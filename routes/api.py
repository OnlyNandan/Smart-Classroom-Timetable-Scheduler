from flask import Blueprint, jsonify, request, session, g
from sqlalchemy import exc

from extensions import db
from models import SchoolGroup, Grade, Stream, Semester, Department, Subject, Course, Teacher, User
from utils import log_activity, validate_json_request, hash_password

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/structure/<mode>', methods=['GET', 'POST'])
@api_bp.route('/structure/<mode>/<int:item_id>', methods=['PUT', 'DELETE'])
def handle_structure_items(mode, item_id=None):
    """API endpoint for handling all structure CRUD operations - handles /api/structure/college calls"""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
    if request.method == 'GET':
        items_data = []
        if mode == 'school':
            groups = SchoolGroup.query.options(db.joinedload('*')).all()
            for group in groups:
                items_data.append({
                    "id": group.id, "name": group.name,
                    "grades": [{"id": g.id, "name": g.name} for g in group.grades],
                    "streams": [{"id": s.id, "name": s.name} for s in group.streams]
                })
        elif mode == 'college':
            semesters = Semester.query.options(db.joinedload('*')).all()
            for sem in semesters:
                items_data.append({
                    "id": sem.id, "name": sem.name,
                    "departments": [{"id": d.id, "name": d.name} for d in sem.departments]
                })
        return jsonify({"items": items_data})
    
    # Handle POST, PUT, DELETE operations
    if request.method in ['POST', 'PUT']:
        data, error_response, status_code = validate_json_request()
        if error_response:
            return error_response, status_code
    
    try:
        if request.method == 'POST':
            if mode == 'school':
                new_group = SchoolGroup(name=data['name'])
                db.session.add(new_group)
                db.session.flush()
                for grade in data.get('grades', []):
                    if grade.get('name'):
                        db.session.add(Grade(name=grade['name'], group_id=new_group.id))
                for stream in data.get('streams', []):
                    if stream.get('name'):
                        db.session.add(Stream(name=stream['name'], group_id=new_group.id))
                db.session.commit()
                log_activity('info', f"School group '{data['name']}' created.")
                return jsonify({"message": "Group created successfully!"})
            else:  # college
                new_sem = Semester(name=data['name'])
                db.session.add(new_sem)
                db.session.flush()
                for dept in data.get('departments', []):
                    if dept.get('name'):
                        db.session.add(Department(name=dept['name'], semester_id=new_sem.id))
                db.session.commit()
                log_activity('info', f"Semester '{data['name']}' created.")
                return jsonify({"message": "Semester created successfully!"})
        
        elif request.method == 'PUT':
            if mode == 'school':
                group = SchoolGroup.query.get_or_404(item_id)
                group.name = data['name']
                
                # Sync Grades
                existing_grades = {g.id: g for g in group.grades}
                updated_grade_ids = {int(g['id']) for g in data['grades'] if g.get('id') and not str(g['id']).startswith('new-')}
                for gid_to_del in existing_grades.keys() - updated_grade_ids:
                    db.session.delete(existing_grades[gid_to_del])
                for g_data in data['grades']:
                    gid = g_data.get('id')
                    if gid and not str(gid).startswith('new-'):
                        existing_grades[int(gid)].name = g_data['name']
                    elif g_data.get('name'):
                        db.session.add(Grade(name=g_data['name'], group_id=group.id))
                
                # Sync Streams
                existing_streams = {s.id: s for s in group.streams}
                updated_stream_ids = {int(s['id']) for s in data['streams'] if s.get('id') and not str(s['id']).startswith('new-')}
                for sid_to_del in existing_streams.keys() - updated_stream_ids:
                    db.session.delete(existing_streams[sid_to_del])
                for s_data in data['streams']:
                    sid = s_data.get('id')
                    if sid and not str(sid).startswith('new-'):
                        existing_streams[int(sid)].name = s_data['name']
                    elif s_data.get('name'):
                        db.session.add(Stream(name=s_data['name'], group_id=group.id))
                
                db.session.commit()
                log_activity('info', f"School group '{group.name}' updated.")
                return jsonify({"message": "Group updated successfully!"})
            else:  # college
                semester = Semester.query.get_or_404(item_id)
                semester.name = data['name']
                
                existing_depts = {d.id: d for d in semester.departments}
                updated_dept_ids = {int(d['id']) for d in data['departments'] if d.get('id') and not str(d['id']).startswith('new-')}
                for did_to_del in existing_depts.keys() - updated_dept_ids:
                    db.session.delete(existing_depts[did_to_del])
                for d_data in data['departments']:
                    did = d_data.get('id')
                    if did and not str(did).startswith('new-'):
                        existing_depts[int(did)].name = d_data['name']
                    elif d_data.get('name'):
                        db.session.add(Department(name=d_data['name'], semester_id=semester.id))
                
                db.session.commit()
                log_activity('info', f"Semester '{semester.name}' updated.")
                return jsonify({"message": "Semester updated successfully!"})
        
        elif request.method == 'DELETE':
            if mode == 'school':
                group = SchoolGroup.query.get_or_404(item_id)
                log_activity('warning', f"School group '{group.name}' deleted.")
                db.session.delete(group)
            else:  # college
                semester = Semester.query.get_or_404(item_id)
                log_activity('warning', f"Semester '{semester.name}' deleted.")
                db.session.delete(semester)
            db.session.commit()
            return jsonify({"message": "Item deleted successfully!"})
            
    except exc.IntegrityError:
        db.session.rollback()
        return jsonify({"message": "Database integrity error. Check for duplicate names or invalid IDs."}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"An unexpected error occurred: {e}"}), 500
    
    return jsonify({"message": "Method not allowed"}), 405

@api_bp.route('/subjects/parents/<mode>', methods=['GET'])
def get_parent_data(mode):
    """API endpoint for getting parent data for subjects - handles /api/subjects/parents/college calls"""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
    parents = []
    if mode == 'school':
        groups = SchoolGroup.query.options(db.joinedload(SchoolGroup.streams)).all()
        for group in groups:
            parents.append({
                "id": group.id,
                "name": group.name,
                "children": [{"id": s.id, "name": s.name} for s in group.streams]
            })
    elif mode == 'college':
        semesters = Semester.query.options(db.joinedload(Semester.departments)).all()
        for sem in semesters:
            parents.append({
                "id": sem.id,
                "name": sem.name,
                "children": [{"id": d.id, "name": d.name} for d in sem.departments]
            })
    return jsonify({"parents": parents})

@api_bp.route('/staff', methods=['GET', 'POST'])
@api_bp.route('/staff/<int:teacher_id>', methods=['PUT', 'DELETE'])
def handle_staff(teacher_id=None):
    """API endpoint for handling all staff CRUD operations - handles /api/staff calls"""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    try:
        if request.method == 'GET':
            teachers = Teacher.query.options(
                db.joinedload(Teacher.user), 
                db.joinedload(Teacher.subjects),
                db.joinedload(Teacher.courses)
            ).all()
            
            teacher_list = []
            for t in teachers:
                subjects = [{"id": s.id, "name": s.name} for s in t.subjects]
                courses = [{"id": c.id, "name": c.name} for c in t.courses]
                all_teachable = subjects + courses

                teacher_list.append({
                    "id": t.id,
                    "full_name": t.full_name,
                    "email": t.user.email,
                    "username": t.user.username,
                    "max_weekly_hours": t.max_weekly_hours,
                    "subjects": all_teachable
                })
            return jsonify({"teachers": teacher_list})

        # Handle POST, PUT operations
        if request.method in ['POST', 'PUT']:
            data, error_response, status_code = validate_json_request()
            if error_response:
                return error_response, status_code
        
        if request.method == 'POST':
            if not data.get('password'): 
                return jsonify({"message": "Password is required for new teachers."}), 400
            if User.query.filter_by(username=data['username']).first(): 
                return jsonify({"message": "Username already exists."}), 409
            if User.query.filter_by(email=data['email']).first(): 
                return jsonify({"message": "Email already exists."}), 409

            new_user = User(username=data['username'], email=data['email'], password=hash_password(data['password']), role='teacher')
            db.session.add(new_user)
            db.session.flush()

            new_teacher = Teacher(full_name=data['full_name'], max_weekly_hours=data['max_weekly_hours'], user_id=new_user.id)
            db.session.add(new_teacher)
            db.session.flush()

            if g.app_mode == 'school':
                new_teacher.subjects = Subject.query.filter(Subject.id.in_(data.get('subject_ids', []))).all()
            else:
                new_teacher.courses = Course.query.filter(Course.id.in_(data.get('subject_ids', []))).all()

            db.session.commit()
            log_activity('info', f"Teacher '{data['full_name']}' created.")
            return jsonify({"message": "Teacher created successfully!"})
        
        teacher = Teacher.query.get_or_404(teacher_id)
        
        if request.method == 'PUT':
            user = teacher.user
            if user.username != data['username'] and User.query.filter_by(username=data['username']).first(): 
                return jsonify({"message": "Username already exists."}), 409
            if user.email != data['email'] and User.query.filter_by(email=data['email']).first(): 
                return jsonify({"message": "Email already exists."}), 409
            
            user.username = data['username']
            user.email = data['email']
            if data.get('password'): 
                user.password = hash_password(data['password'])
            
            teacher.full_name = data['full_name']
            teacher.max_weekly_hours = data['max_weekly_hours']

            if g.app_mode == 'school':
                teacher.subjects = Subject.query.filter(Subject.id.in_(data.get('subject_ids', []))).all()
                teacher.courses = []
            else:
                teacher.courses = Course.query.filter(Course.id.in_(data.get('subject_ids', []))).all()
                teacher.subjects = []

            db.session.commit()
            log_activity('info', f"Teacher '{teacher.full_name}' updated.")
            return jsonify({"message": "Teacher updated successfully!"})

        if request.method == 'DELETE':
            user_to_delete = teacher.user
            db.session.delete(teacher)
            db.session.delete(user_to_delete)
            db.session.commit()
            log_activity('warning', f"Teacher '{teacher.full_name}' deleted.")
            return jsonify({"message": "Teacher deleted successfully!"})

    except exc.IntegrityError as e:
        db.session.rollback()
        return jsonify({"message": "Database integrity error occurred."}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"An unexpected error occurred: {e}"}), 500

@api_bp.route('/subjects/<mode>', methods=['GET', 'POST'])
@api_bp.route('/subjects/<mode>/<int:item_id>', methods=['PUT', 'DELETE'])
def handle_subjects(mode, item_id=None):
    """API endpoint for handling all subjects CRUD operations - handles /api/subjects/college calls"""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
    try:
        if request.method == 'GET':
            parent_id = request.args.get('parent_id', type=int)
            if not parent_id:
                return jsonify({"items": []})
            
            response = {"items": []}
            if mode == 'school':
                subjects = Subject.query.filter_by(stream_id=parent_id).all()
                response['items'] = [
                    {"id": s.id, "name": s.name, "code": s.code, "weekly_hours": s.weekly_hours, "is_elective": s.is_elective, "stream_id": s.stream_id} for s in subjects
                ]
            elif mode == 'college':
                courses = Course.query.filter_by(department_id=parent_id).all()
                response['items'] = [
                    {"id": c.id, "name": c.name, "code": c.code, "credits": c.credits, "course_type": c.course_type, "department_id": c.department_id} for c in courses
                ]
            return jsonify(response)

        # Handle POST, PUT operations
        if request.method in ['POST', 'PUT']:
            data, error_response, status_code = validate_json_request()
            if error_response:
                return error_response, status_code

        if request.method == 'POST':
            code = data.get('code')
            if not code: 
                return jsonify({"message": "Code is a required field."}), 400

            if mode == 'school':
                if Subject.query.filter_by(code=code).first():
                    return jsonify({"message": f"Subject code '{code}' already exists."}), 409
                new_item = Subject(name=data['name'], code=code, weekly_hours=data['weekly_hours'], is_elective=data.get('is_elective', False), stream_id=data['stream_id'])
                db.session.add(new_item)
            else:  # college
                if Course.query.filter_by(code=code).first():
                    return jsonify({"message": f"Course code '{code}' already exists."}), 409
                new_item = Course(name=data['name'], code=code, credits=data['credits'], course_type=data['course_type'], department_id=data['department_id'])
                db.session.add(new_item)
            
            log_activity('info', f"{'Subject' if mode == 'school' else 'Course'} '{data['name']}' created.")
            message = f"{'Subject' if mode == 'school' else 'Course'} created successfully!"

        else:  # PUT or DELETE
            item = Subject.query.get_or_404(item_id) if mode == 'school' else Course.query.get_or_404(item_id)

            if request.method == 'PUT':
                new_code = data.get('code')
                if not new_code: 
                    return jsonify({"message": "Code is a required field."}), 400
                if item.code != new_code:
                    if (mode == 'school' and Subject.query.filter_by(code=new_code).first()) or \
                       (mode == 'college' and Course.query.filter_by(code=new_code).first()):
                        return jsonify({"message": f"{'Subject' if mode == 'school' else 'Course'} code '{new_code}' already exists."}), 409
                
                item.name = data['name']
                item.code = new_code
                if mode == 'school':
                    item.weekly_hours = data['weekly_hours']
                    item.is_elective = data.get('is_elective', False)
                else:  # college
                    item.credits = data['credits']
                    item.course_type = data['course_type']
                
                log_activity('info', f"{'Subject' if mode == 'school' else 'Course'} '{item.name}' updated.")
                message = f"{'Subject' if mode == 'school' else 'Course'} updated successfully!"

            elif request.method == 'DELETE':
                db.session.delete(item)
                log_activity('warning', f"{'Subject' if mode == 'school' else 'Course'} '{item.name}' deleted.")
                message = f"{'Subject' if mode == 'school' else 'Course'} deleted successfully!"

        db.session.commit()
        return jsonify({"message": message})

    except exc.IntegrityError:
        db.session.rollback()
        return jsonify({"message": "Database integrity error. Check for duplicate codes or invalid IDs."}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"An unexpected error occurred: {e}"}), 500

@api_bp.route('/staff/all_subjects', methods=['GET'])
def get_all_subjects_for_staff():
    """API endpoint for getting all subjects for staff - handles /api/staff/all_subjects calls"""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
    try:
        subjects_list = []
        if g.app_mode == 'school':
            subjects = Subject.query.order_by(Subject.name).all()
            subjects_list = [{"id": s.id, "name": s.name, "code": s.code, "type": "subject"} for s in subjects]
        else:
            courses = Course.query.order_by(Course.name).all()
            subjects_list = [{"id": c.id, "name": c.name, "code": c.code, "type": "course"} for c in courses]
            
        return jsonify({"subjects": subjects_list})
    except Exception as e:
        return jsonify({"message": f"Error fetching subjects: {str(e)}"}), 500

from flask import Blueprint, jsonify, request, session, redirect, url_for, render_template
from sqlalchemy import exc

from extensions import db
from models import SchoolGroup, Semester, Subject, Course
from utils import log_activity

subjects_bp = Blueprint('subjects', __name__, url_prefix='/subjects')
# API-prefixed blueprint to serve endpoints under /api/subjects
subjects_api_bp = Blueprint('subjects_api', __name__, url_prefix='/api/subjects')

@subjects_bp.route('/')
def manage_subjects():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    return render_template('subjects.html')

@subjects_bp.route('/api/parents/<mode>', methods=['GET'])
@subjects_api_bp.route('/parents/<mode>', methods=['GET'])
def get_parent_data(mode):
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

@subjects_bp.route('/api/<mode>', methods=['GET'])
@subjects_api_bp.route('/<mode>', methods=['GET'])
def get_subjects_data(mode):
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
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

@subjects_bp.route('/api/<mode>', methods=['POST'])
@subjects_bp.route('/api/<mode>/<int:item_id>', methods=['PUT', 'DELETE'])
@subjects_api_bp.route('/<mode>', methods=['POST'])
@subjects_api_bp.route('/<mode>/<int:item_id>', methods=['PUT', 'DELETE'])
def handle_subjects(mode, item_id=None):
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
    data = request.json if request.method in ['POST', 'PUT'] else None

    try:
        if request.method == 'POST':
            code = data.get('code')
            if not code: return jsonify({"message": "Code is a required field."}), 400

            if mode == 'school':
                if Subject.query.filter_by(code=code).first():
                    return jsonify({"message": f"Subject code '{code}' already exists."}), 409
                new_item = Subject(name=data['name'], code=code, weekly_hours=data['weekly_hours'], is_elective=data.get('is_elective', False), stream_id=data['stream_id'])
                db.session.add(new_item)
            else: # college
                if Course.query.filter_by(code=code).first():
                    return jsonify({"message": f"Course code '{code}' already exists."}), 409
                new_item = Course(name=data['name'], code=code, credits=data['credits'], course_type=data['course_type'], department_id=data['department_id'])
                db.session.add(new_item)
            
            log_activity('info', f"{'Subject' if mode == 'school' else 'Course'} '{data['name']}' created.")
            message = f"{'Subject' if mode == 'school' else 'Course'} created successfully!"

        else: # PUT or DELETE
            item = Subject.query.get_or_404(item_id) if mode == 'school' else Course.query.get_or_404(item_id)

            if request.method == 'PUT':
                new_code = data.get('code')
                if not new_code: return jsonify({"message": "Code is a required field."}), 400
                if item.code != new_code:
                    if (mode == 'school' and Subject.query.filter_by(code=new_code).first()) or \
                       (mode == 'college' and Course.query.filter_by(code=new_code).first()):
                        return jsonify({"message": f"{'Subject' if mode == 'school' else 'Course'} code '{new_code}' already exists."}), 409
                
                item.name = data['name']
                item.code = new_code
                if mode == 'school':
                    item.weekly_hours = data['weekly_hours']
                    item.is_elective = data.get('is_elective', False)
                else: # college
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

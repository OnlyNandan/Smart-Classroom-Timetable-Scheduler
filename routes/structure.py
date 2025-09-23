from flask import Blueprint, jsonify, request, session, redirect, url_for, render_template

from extensions import db
from models import SchoolGroup, Grade, Stream, Semester, Department
from utils import log_activity

structure_bp = Blueprint('structure', __name__, url_prefix='/structure')

@structure_bp.route('/')
def manage_structure():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    return render_template('structure.html')

@structure_bp.route('/api/<mode>', methods=['GET'])
def get_structure_items(mode):
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
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

@structure_bp.route('/api/school', methods=['POST'])
@structure_bp.route('/api/school/<int:item_id>', methods=['PUT', 'DELETE'])
def handle_school_structure(item_id=None):
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
    if request.method == 'POST': # Create New
        data = request.json
        new_group = SchoolGroup(name=data['name'])
        db.session.add(new_group)
        db.session.flush() # Get the ID for relationships
        for grade in data.get('grades', []):
            if grade.get('name'):
                db.session.add(Grade(name=grade['name'], group_id=new_group.id))
        for stream in data.get('streams', []):
            if stream.get('name'):
                db.session.add(Stream(name=stream['name'], group_id=new_group.id))
        db.session.commit()
        log_activity('info', f"School group '{data['name']}' created.")
        return jsonify({"message": "Group created successfully!"})

    group = SchoolGroup.query.get_or_404(item_id)
    if request.method == 'PUT': # Update Existing
        data = request.json
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
        
    if request.method == 'DELETE':
        log_activity('warning', f"School group '{group.name}' deleted.")
        db.session.delete(group)
        db.session.commit()
        return jsonify({"message": "Group deleted successfully!"})
    return jsonify({"message": "Method not allowed"}), 405


@structure_bp.route('/api/college', methods=['POST'])
@structure_bp.route('/api/college/<int:item_id>', methods=['PUT', 'DELETE'])
def handle_college_structure(item_id=None):
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    if request.method == 'POST':
        data = request.json
        new_sem = Semester(name=data['name'])
        db.session.add(new_sem)
        db.session.flush()
        for dept in data.get('departments', []):
            if dept.get('name'):
                db.session.add(Department(name=dept['name'], semester_id=new_sem.id))
        db.session.commit()
        log_activity('info', f"Semester '{data['name']}' created.")
        return jsonify({"message": "Semester created successfully!"})

    semester = Semester.query.get_or_404(item_id)
    if request.method == 'PUT':
        data = request.json
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

    if request.method == 'DELETE':
        log_activity('warning', f"Semester '{semester.name}' deleted.")
        db.session.delete(semester)
        db.session.commit()
        return jsonify({"message": "Semester deleted successfully!"})
    return jsonify({"message": "Method not allowed"}), 405

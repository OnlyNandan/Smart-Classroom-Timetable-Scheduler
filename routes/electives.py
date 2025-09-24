from flask import Blueprint, render_template, request, jsonify, session
from models import db, Subject, Student, StudentSection
from sqlalchemy.orm import joinedload

electives_bp = Blueprint('electives', __name__, url_prefix='/electives')

@electives_bp.route('/')
def manage_electives():
    """Manage elective subjects for students"""
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    return render_template('electives.html')

@electives_bp.route('/api/status', methods=['GET'])
def handle_elective_status():
    """Get elective status for students"""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        # Get all elective subjects
        electives = Subject.query.filter_by(is_elective=True).all()
        
        # Get students with their elective choices
        students = Student.query.options(
            joinedload(Student.electives),
            joinedload(Student.section)
        ).all()
        
        data = {
            'electives': [{'id': e.id, 'name': e.name, 'code': e.code} for e in electives],
            'students': []
        }
        
        for student in students:
            student_data = {
                'id': student.id,
                'name': student.full_name,
                'section': student.section.name if student.section else 'No Section',
                'electives': [{'id': e.id, 'name': e.name} for e in student.electives]
            }
            data['students'].append(student_data)
        
        return jsonify(data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@electives_bp.route('/api/data', methods=['GET'])
def get_electives_data():
    """Get electives data for management"""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        # Get all elective subjects
        electives = Subject.query.filter_by(is_elective=True).all()
        
        # Get students with their sections
        students = Student.query.options(
            joinedload(Student.section)
        ).all()
        
        data = {
            'electives': [{'id': e.id, 'name': e.name, 'code': e.code} for e in electives],
            'students': [{'id': s.id, 'name': s.full_name, 'section': s.section.name if s.section else 'No Section'} for s in students]
        }
        
        return jsonify(data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@electives_bp.route('/api/assign', methods=['POST'])
def assign_electives():
    """Assign elective subjects to students"""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        elective_ids = data.get('elective_ids', [])
        
        if not student_id:
            return jsonify({"error": "Student ID required"}), 400
        
        student = Student.query.get(student_id)
        if not student:
            return jsonify({"error": "Student not found"}), 404
        
        # Get elective subjects
        electives = Subject.query.filter(Subject.id.in_(elective_ids), Subject.is_elective == True).all()
        
        # Clear existing electives and assign new ones
        student.electives.clear()
        student.electives.extend(electives)
        
        db.session.commit()
        
        return jsonify({"message": "Electives assigned successfully"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

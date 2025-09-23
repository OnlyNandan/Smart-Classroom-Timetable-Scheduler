from flask import Blueprint, jsonify, request, session, redirect, url_for, render_template, g
from sqlalchemy import exc

from extensions import db
from models import User, Teacher, Subject, Course
from utils import hash_password, log_activity

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')

@staff_bp.route('/')
def manage_staff():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    return render_template('staff.html')

@staff_bp.route('/api/all_subjects', methods=['GET'])
def get_all_subjects_for_staff():
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
    subjects_list = []
    if g.app_mode == 'school':
        subjects = Subject.query.order_by(Subject.name).all()
        subjects_list = [{"id": s.id, "name": s.name, "code": s.code, "type": "subject"} for s in subjects]
    else:
        courses = Course.query.order_by(Course.name).all()
        subjects_list = [{"id": c.id, "name": c.name, "code": c.code, "type": "course"} for c in courses]
        
    return jsonify({"subjects": subjects_list})

@staff_bp.route('/api', methods=['GET', 'POST'])
@staff_bp.route('/api/<int:teacher_id>', methods=['PUT', 'DELETE'])
def handle_staff(teacher_id=None):
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

        data = request.json
        
        if request.method == 'POST':
            if not data.get('password'): return jsonify({"message": "Password is required for new teachers."}), 400
            if User.query.filter_by(username=data['username']).first(): return jsonify({"message": "Username already exists."}), 409
            if User.query.filter_by(email=data['email']).first(): return jsonify({"message": "Email already exists."}), 409

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
            if user.username != data['username'] and User.query.filter_by(username=data['username']).first(): return jsonify({"message": "Username already exists."}), 409
            if user.email != data['email'] and User.query.filter_by(email=data['email']).first(): return jsonify({"message": "Email already exists."}), 409
            
            user.username = data['username']
            user.email = data['email']
            if data.get('password'): user.password = hash_password(data['password'])
            
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

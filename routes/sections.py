import io
import csv
import random
from flask import Blueprint, jsonify, request, session, redirect, url_for, render_template, g
from sqlalchemy import exc

from extensions import db
from models import User, Student, StudentSection
from utils import hash_password, generate_random_password, log_activity

sections_bp = Blueprint('sections', __name__)
# API-prefixed blueprint to serve endpoints under /api/sections and /api/students
sections_api_bp = Blueprint('sections_api', __name__, url_prefix='/api')

@sections_bp.route('/sections')
def manage_sections():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    return render_template('sections.html')

@sections_bp.route('/api/sections', methods=['GET', 'POST'])
@sections_bp.route('/api/sections/<int:section_id>', methods=['PUT', 'DELETE'])
@sections_api_bp.route('/sections', methods=['GET', 'POST'])
@sections_api_bp.route('/sections/<int:section_id>', methods=['PUT', 'DELETE'])
def handle_sections(section_id=None):
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
    try:
        if request.method == 'GET':
            parent_id = request.args.get('parent_id', type=int)
            if not parent_id: return jsonify({"sections": []})
            
            query = StudentSection.query.options(db.joinedload(StudentSection.students).joinedload(Student.user))
            if g.app_mode == 'school':
                sections = query.filter_by(grade_id=parent_id).order_by(StudentSection.name).all()
            else: # college
                sections = query.filter_by(department_id=parent_id).order_by(StudentSection.name).all()

            section_list = []
            for s in sections:
                section_list.append({
                    "id": s.id, "name": s.name, "capacity": s.capacity,
                    "students": sorted([{"id": stu.id, "full_name": stu.full_name, "user": {"username": stu.user.username, "email": stu.user.email}} for stu in s.students], key=lambda x: x['full_name'])
                })
            return jsonify({"sections": section_list})

        data = request.json
        if request.method in ['POST', 'PUT'] and (not data.get('name') or data.get('capacity') is None):
            return jsonify({"message": "Name and Capacity are required."}), 400

        if request.method == 'POST':
            new_section = StudentSection(name=data['name'], capacity=data['capacity'])
            if g.app_mode == 'school': new_section.grade_id = data['grade_id']
            else: new_section.department_id = data['department_id']
            db.session.add(new_section)
            message = f"{'Section' if g.app_mode == 'school' else 'Batch'} created."
            log_activity('info', message)

        else: # PUT or DELETE
            section = StudentSection.query.get_or_404(section_id)
            if request.method == 'PUT':
                section.name = data['name']
                section.capacity = data['capacity']
                message = f"{'Section' if g.app_mode == 'school' else 'Batch'} updated."
                log_activity('info', f"{'Section' if g.app_mode == 'school' else 'Batch'} '{section.name}' updated.")
            
            elif request.method == 'DELETE':
                for student in section.students: student.section_id = None
                db.session.delete(section)
                message = f"{'Section' if g.app_mode == 'school' else 'Batch'} deleted."
                log_activity('warning', f"Section '{section.name}' deleted.")
        
        db.session.commit()
        return jsonify({"message": message})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "An unexpected server error occurred."}), 500

@sections_bp.route('/api/students', methods=['POST'])
@sections_bp.route('/api/students/<int:student_id>', methods=['PUT', 'DELETE'])
@sections_api_bp.route('/students', methods=['POST'])
@sections_api_bp.route('/students/<int:student_id>', methods=['PUT', 'DELETE'])
def handle_students(student_id=None):
    if 'user_id' not in session: return jsonify({"message": "Unauthorized"}), 401

    try:
        data = request.json if request.method in ['POST', 'PUT'] else None
        if request.method in ['POST', 'PUT']:
            if not data.get('full_name') or not data.get('username') or not data.get('section_id'):
                return jsonify({"message": "Full Name, Username, and Section are required."}), 400

        if request.method == 'POST':
            if not data.get('password'): return jsonify({"message": "Password is required for new students."}), 400
            if User.query.filter_by(username=data['username']).first(): return jsonify({"message": "Username already exists."}), 409
            if data.get('email') and User.query.filter_by(email=data['email']).first(): return jsonify({"message": "Email already exists."}), 409

            new_user = User(username=data['username'], email=data.get('email'), password=hash_password(data['password']), role='student')
            db.session.add(new_user)
            db.session.flush()

            new_student = Student(full_name=data['full_name'], section_id=data['section_id'], user_id=new_user.id)
            db.session.add(new_student)
            message = "Student created successfully."
            log_activity('info', f"Student '{data['full_name']}' created.")

        else: # PUT or DELETE
            student = Student.query.get_or_404(student_id)
            user = student.user

            if request.method == 'PUT':
                if user.username != data['username'] and User.query.filter_by(username=data['username']).first(): return jsonify({"message": "Username already exists."}), 409
                if data.get('email') and user.email != data['email'] and User.query.filter_by(email=data['email']).first(): return jsonify({"message": "Email already exists."}), 409
                
                user.username, user.email = data['username'], data.get('email')
                if data.get('password'): user.password = hash_password(data['password'])
                
                student.full_name, student.section_id = data['full_name'], data['section_id']
                message = "Student updated successfully."
                log_activity('info', f"Student '{student.full_name}' updated.")

            elif request.method == 'DELETE':
                db.session.delete(user) # Deleting user cascades to student
                message = "Student deleted successfully."
                log_activity('warning', f"Student '{student.full_name}' deleted.")

        db.session.commit()
        return jsonify({"message": message})
        
    except exc.IntegrityError:
        db.session.rollback()
        return jsonify({"message": "Database integrity error. Check for duplicate data."}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"An unexpected error occurred: {e}"}), 500

@sections_bp.route('/api/students/bulk_upload', methods=['POST'])
@sections_api_bp.route('/students/bulk_upload', methods=['POST'])
def bulk_upload_students():
    if 'user_id' not in session: return jsonify({"message": "Unauthorized"}), 401
    if 'file' not in request.files: return jsonify({"message": "No file part"}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"message": "No selected file"}), 400
    
    parent_id = request.form.get('parent_id', type=int)
    if not parent_id: return jsonify({"message": "No Grade/Department selected."}), 400

    if file and file.filename.endswith('.csv'):
        try:
            if g.app_mode == 'school': sections_query = StudentSection.query.filter_by(grade_id=parent_id).all()
            else: sections_query = StudentSection.query.filter_by(department_id=parent_id).all()
            sections_map = {s.name.lower(): s.id for s in sections_query}

            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.reader(stream)
            next(csv_reader, None) # Skip header

            imported_count, failed_count = 0, 0
            
            for row in csv_reader:
                try:
                    full_name, section_name = row[0].strip(), row[1].strip()
                    email = row[2].strip() if len(row) > 2 and row[2].strip() else None

                    section_id = sections_map.get(section_name.lower())
                    if not full_name or not section_id: raise ValueError("Missing data")

                    username = "".join(full_name.lower().split())
                    if User.query.filter_by(username=username).first(): username = f"{username}{random.randint(10, 99)}"
                    if email and User.query.filter_by(email=email).first(): raise ValueError("Email exists")
                    
                    with db.session.begin_nested():
                        new_user = User(username=username, email=email, password=hash_password(generate_random_password()), role='student')
                        db.session.add(new_user); db.session.flush()
                        new_student = Student(full_name=full_name, section_id=section_id, user_id=new_user.id)
                        db.session.add(new_student)
                    imported_count += 1
                except Exception:
                    failed_count += 1
                    continue

            db.session.commit()
            log_activity('info', f"Bulk imported {imported_count} students. {failed_count} rows failed.")
            return jsonify({"message": f"Successfully imported {imported_count} students. Failed rows: {failed_count}."})
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": f"An error occurred during processing: {e}"}), 500
    return jsonify({"message": "Invalid file type. Please upload a CSV."}), 400

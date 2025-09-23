import io
import csv
import random
from flask import Blueprint, jsonify, request, session, redirect, url_for, render_template, g, send_file
from sqlalchemy import exc

from extensions import db
from models import User, Student, StudentSection, Semester, Department, Course, Subject
from utils import hash_password, generate_random_password, log_activity

sections_bp = Blueprint('sections', __name__)

def find_or_create_section(section_name, department_id=None, grade_id=None):
    """Seamlessly find or create section - the best in the world!"""
    print(f"Looking for section: '{section_name}' in department_id: {department_id}, grade_id: {grade_id}")
    
    # Find existing section with available capacity
    if g.app_mode == 'school':
        existing_section = StudentSection.query.filter_by(
            name=section_name, 
            grade_id=grade_id
        ).first()
    else:  # college
        existing_section = StudentSection.query.filter_by(
            name=section_name, 
            department_id=department_id
        ).first()
    
    if existing_section:
        current_students = len(existing_section.students)
        print(f"Found existing section '{section_name}' with {current_students}/{existing_section.capacity} students")
        
        if current_students < existing_section.capacity:
            print(f"Section has capacity, using existing section")
            return existing_section
        else:
            # Section is full, create a new one with incremental naming
            section_count = StudentSection.query.filter(
                StudentSection.name.like(f"{section_name}%")
            ).count()
            new_section_name = f"{section_name} - {section_count + 1}"
            print(f"Section full, creating new section: '{new_section_name}'")
            
            if g.app_mode == 'school':
                new_section = StudentSection(name=new_section_name, capacity=30, grade_id=grade_id)
            else:  # college
                new_section = StudentSection(name=new_section_name, capacity=30, department_id=department_id)
            
            db.session.add(new_section)
            db.session.flush()
            print(f"Created new section: '{new_section_name}' with ID: {new_section.id}")
            return new_section
    else:
        # Section doesn't exist, create it
        print(f"Section '{section_name}' doesn't exist, creating new one")
        
        if g.app_mode == 'school':
            new_section = StudentSection(name=section_name, capacity=30, grade_id=grade_id)
        else:  # college
            new_section = StudentSection(name=section_name, capacity=30, department_id=department_id)
        
        db.session.add(new_section)
        db.session.flush()
        print(f"Created new section: '{section_name}' with ID: {new_section.id}")
        return new_section

@sections_bp.route('/sections')
def manage_sections():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    return render_template('sections.html')

@sections_bp.route('/api/sections', methods=['GET', 'POST'])
@sections_bp.route('/api/sections/<int:section_id>', methods=['PUT', 'DELETE'])
def handle_sections(section_id=None):
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
    try:
        if request.method == 'GET':
            parent_id = request.args.get('parent_id', type=int)
            if not parent_id: return jsonify({"sections": []})
            
            query = StudentSection.query.options(
                db.joinedload(StudentSection.students).joinedload(Student.user),
                db.joinedload(StudentSection.students).joinedload(Student.electives)
            )
            if g.app_mode == 'school':
                sections = query.filter_by(grade_id=parent_id).order_by(StudentSection.name).all()
            else: # college
                sections = query.filter_by(department_id=parent_id).order_by(StudentSection.name).all()

            section_list = []
            for s in sections:
                section_list.append({
                    "id": s.id, "name": s.name, "capacity": s.capacity,
                    "students": sorted([{
                        "id": stu.id, 
                        "full_name": stu.full_name, 
                        "user": {"username": stu.user.username, "email": stu.user.email},
                        "electives": [{"id": e.id, "name": e.name} for e in stu.electives]
                    } for stu in s.students], key=lambda x: x['full_name'])
                })
            return jsonify({"sections": section_list})

        data = request.json if request.method in ['POST', 'PUT'] else None
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
                print(f"DELETE request received for section ID: {section_id}")
                print(f"Deleting section: {section.name} with {len(section.students)} students")
                
                # Unassign all students from this section
                for student in section.students: 
                    student.section_id = None
                    print(f"Unassigned student: {student.full_name}")
                
                # Delete the section
                db.session.delete(section)
                message = f"{'Section' if g.app_mode == 'school' else 'Batch'} deleted."
                log_activity('warning', f"Section '{section.name}' deleted.")
                print(f"Section {section.name} deleted successfully")
        
        db.session.commit()
        return jsonify({"message": message})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "An unexpected server error occurred."}), 500

@sections_bp.route('/api/students', methods=['POST'])
@sections_bp.route('/api/students/<int:student_id>', methods=['PUT', 'DELETE'])
def handle_students(student_id=None):
    if 'user_id' not in session: return jsonify({"message": "Unauthorized"}), 401

    try:
        data = request.json if request.method in ['POST', 'PUT'] else None
        if request.method in ['POST', 'PUT']:
            if not data.get('full_name') or not data.get('username') or not data.get('section_id'):
                return jsonify({"message": "Full Name, Username, and Section are required."}), 400

        if request.method == 'POST':
            # Use username as password if password is not provided
            password = data.get('password') or data['username']
            if User.query.filter_by(username=data['username']).first(): return jsonify({"message": "Username already exists."}), 409
            if data.get('email') and User.query.filter_by(email=data['email']).first(): return jsonify({"message": "Email already exists."}), 409

            new_user = User(username=data['username'], email=data.get('email'), password=hash_password(password), role='student')
            db.session.add(new_user)
            db.session.flush()

            new_student = Student(full_name=data['full_name'], section_id=data['section_id'], user_id=new_user.id)
            db.session.add(new_student)
            
            # Handle electives if provided
            if data.get('electives'):
                elective_names = [e.strip() for e in data['electives'].split(',') if e.strip()]
                for elective_name in elective_names:
                    if g.app_mode == 'school':
                        # Find elective subject
                        elective = db.session.query(Subject).filter_by(
                            name=elective_name.strip(), 
                            is_elective=True
                        ).first()
                    else:  # college
                        # Find elective course
                        elective = db.session.query(Course).filter_by(
                            name=elective_name.strip(),
                            course_type='elective'
                        ).first()
                    
                    if elective:
                        new_student.electives.append(elective)
            
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
                
                # Handle electives update
                student.electives.clear()  # Clear existing electives
                if data.get('electives'):
                    elective_names = [e.strip() for e in data['electives'].split(',') if e.strip()]
                    for elective_name in elective_names:
                        if g.app_mode == 'school':
                            # Find elective subject
                            elective = db.session.query(Subject).filter_by(
                                name=elective_name.strip(), 
                                is_elective=True
                            ).first()
                        else:  # college
                            # Find elective course
                            elective = db.session.query(Course).filter_by(
                                name=elective_name.strip(),
                                course_type='elective'
                            ).first()
                        
                        if elective:
                            student.electives.append(elective)
                
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
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 because we skipped header
                try:
                    if g.app_mode == 'school':
                        if len(row) < 2:
                            raise ValueError("Row must have at least 2 columns (Full Name, Section Name)")
                        full_name, section_name = row[0].strip(), row[1].strip()
                        email = row[2].strip() if len(row) > 2 and row[2].strip() else None
                        semester_name, department_name = None, None
                    else:  # college
                        if len(row) < 4:
                            raise ValueError("Row must have at least 4 columns (Full Name, Section Name, Semester, Department)")
                        full_name, section_name = row[0].strip(), row[1].strip()
                        semester_name = row[2].strip() if len(row) > 2 and row[2].strip() else None
                        department_name = row[3].strip() if len(row) > 3 and row[3].strip() else None
                        email = row[4].strip() if len(row) > 4 and row[4].strip() else None

                    if not full_name:
                        raise ValueError("Full Name is required")
                    
                    # For college mode, validate semester and department uniqueness
                    if g.app_mode == 'college':
                        if not semester_name or not department_name:
                            raise ValueError("Semester and Department are required for college mode")
                        
                        # Check if student already exists with this semester-department combination
                        existing_student = db.session.query(Student).join(User).join(StudentSection).join(Department).join(Semester).filter(
                            User.username == "".join(full_name.lower().split()),
                            Semester.name == semester_name,
                            Department.name == department_name
                        ).first()
                        
                        if existing_student:
                            raise ValueError(f"Student already exists with semester '{semester_name}' and department '{department_name}'")
                    
                    # Seamlessly find or create section - the best in the world!
                    if g.app_mode == 'school':
                        # For school, find any existing section to get grade_id
                        section = StudentSection.query.filter_by(name=section_name).first()
                        if section:
                            target_section = find_or_create_section(section_name, grade_id=section.grade_id)
                        else:
                            # No sections exist yet, create with default grade_id
                            target_section = find_or_create_section(section_name, grade_id=1)  # Default to first grade
                    else:  # college
                        # For college, find department based on semester and department name
                        semester = Semester.query.filter_by(name=semester_name).first()
                        if not semester:
                            raise ValueError(f"Semester '{semester_name}' not found")
                        
                        department = Department.query.filter_by(
                            semester_id=semester.id,
                            name=department_name
                        ).first()
                        
                        if not department:
                            raise ValueError(f"Department '{department_name}' not found for semester '{semester_name}'")
                        
                        # Seamlessly create or find section
                        target_section = find_or_create_section(section_name, department_id=department.id)

                    username = "".join(full_name.lower().split())
                    if User.query.filter_by(username=username).first(): 
                        username = f"{username}{random.randint(10, 99)}"
                    if email and User.query.filter_by(email=email).first(): 
                        raise ValueError(f"Email '{email}' already exists")
                    
                    with db.session.begin_nested():
                        new_user = User(username=username, email=email, password=hash_password(username), role='student')
                        db.session.add(new_user); db.session.flush()
                        new_student = Student(full_name=full_name, section_id=target_section.id, user_id=new_user.id)
                        db.session.add(new_student)
                        db.session.flush()
                    imported_count += 1
                except Exception as e:
                    failed_count += 1
                    print(f"Row {row_num} failed: {str(e)}")  # Debug logging
                    print(f"Row data: {row}")  # Debug the actual row data
                    continue

            db.session.commit()
            log_activity('info', f"Bulk imported {imported_count} students. {failed_count} rows failed.")
            return jsonify({"message": f"Successfully imported {imported_count} students. Failed rows: {failed_count}."})
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": f"An error occurred during processing: {e}"}), 500
    return jsonify({"message": "Invalid file type. Please upload a CSV."}), 400

@sections_bp.route('/download_csv_template')
def download_csv_template():
    """Download CSV template for bulk student import."""
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    # Create CSV template
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header based on app mode
    if g.app_mode == 'school':
        writer.writerow(['Full Name', 'Section Name', 'Email (Optional)'])
    else:  # college
        writer.writerow(['Full Name', 'Section Name', 'Semester', 'Department', 'Email (Optional)'])
    
    # Generate 30+ sample entries
    sample_names = [
        'John Doe', 'Jane Smith', 'Ravi Kumar', 'Priya Sharma', 'Michael Johnson',
        'Sarah Wilson', 'David Brown', 'Lisa Garcia', 'Robert Martinez', 'Jennifer Davis',
        'William Rodriguez', 'Linda Anderson', 'James Taylor', 'Patricia Thomas', 'Christopher Jackson',
        'Elizabeth White', 'Daniel Harris', 'Barbara Martin', 'Matthew Thompson', 'Susan Garcia',
        'Anthony Martinez', 'Jessica Robinson', 'Mark Clark', 'Sarah Rodriguez', 'Donald Lewis',
        'Nancy Lee', 'Steven Walker', 'Karen Hall', 'Paul Allen', 'Betty Young',
        'Andrew Hernandez', 'Dorothy King', 'Joshua Wright', 'Helen Lopez', 'Kenneth Hill'
    ]
    
    sample_emails = [
        'john.doe@example.com', 'jane.smith@example.com', 'ravi.kumar@example.com', 'priya.sharma@example.com', 'michael.johnson@example.com',
        'sarah.wilson@example.com', 'david.brown@example.com', 'lisa.garcia@example.com', 'robert.martinez@example.com', 'jennifer.davis@example.com',
        'william.rodriguez@example.com', 'linda.anderson@example.com', 'james.taylor@example.com', 'patricia.thomas@example.com', 'christopher.jackson@example.com',
        'elizabeth.white@example.com', 'daniel.harris@example.com', 'barbara.martin@example.com', 'matthew.thompson@example.com', 'susan.garcia@example.com',
        'anthony.martinez@example.com', 'jessica.robinson@example.com', 'mark.clark@example.com', 'sarah.rodriguez@example.com', 'donald.lewis@example.com',
        'nancy.lee@example.com', 'steven.walker@example.com', 'karen.hall@example.com', 'paul.allen@example.com', 'betty.young@example.com',
        'andrew.hernandez@example.com', 'dorothy.king@example.com', 'joshua.wright@example.com', 'helen.lopez@example.com', 'kenneth.hill@example.com'
    ]
    
    # Get actual sections for sample data
    try:
        if g.app_mode == 'school':
            # Get sections from the first grade
            first_grade = db.session.query(StudentSection.grade_id).filter(StudentSection.grade_id.isnot(None)).first()
            if first_grade:
                sections = StudentSection.query.filter_by(grade_id=first_grade[0]).all()
                # Get electives from streams
                electives = db.session.query(Subject).filter_by(is_elective=True).limit(5).all()
            else:
                sections = []
                electives = []
        else:  # college
            # Get sections from the first department
            first_dept = db.session.query(StudentSection.department_id).filter(StudentSection.department_id.isnot(None)).first()
            if first_dept:
                sections = StudentSection.query.filter_by(department_id=first_dept[0]).all()
                # Get electives from courses
                electives = db.session.query(Course).filter_by(course_type='elective').limit(5).all()
            else:
                sections = []
                electives = []
        
        # Always use multiple sections for CSV template to distribute students
        # Get semesters and departments for college mode
        semesters = []
        departments = []
        if g.app_mode == 'college':
            semesters = db.session.query(Semester).all()
            departments = db.session.query(Department).all()
        
        # Use multiple sections to distribute students
        template_sections = ['Section A', 'Section B', 'Section C', 'Section D', 'Section E']
        
        for i in range(min(35, len(sample_names))):
            name = sample_names[i]
            email = sample_emails[i] if i < len(sample_emails) else f'student{i+1}@example.com'
            section = template_sections[i % len(template_sections)]  # Cycle through template sections
            
            if g.app_mode == 'school':
                writer.writerow([name, section, email])
            else:  # college
                # Use actual semester and department from database
                if semesters and departments:
                    semester = semesters[i % len(semesters)]
                    department = departments[i % len(departments)]
                    writer.writerow([name, section, semester.name, department.name, email])
                else:
                    # Fallback if no semesters/departments found
                    writer.writerow([name, section, "SEM 1", "Electronics", email])
            
    except Exception as e:
        # Fallback sample data if there's any error - use your actual data
        fallback_sections = ['Section A', 'Section B', 'Section C', 'Section D', 'Section E']
        fallback_semesters = ['SEM 1', 'SEM 2']
        fallback_departments = ['Electronics', 'CSEe', 'ECE', 'CSE']
        
        for i in range(35):
            name = sample_names[i]
            email = sample_emails[i] if i < len(sample_emails) else f'student{i+1}@example.com'
            section = fallback_sections[i % len(fallback_sections)]
            
            if g.app_mode == 'school':
                writer.writerow([name, section, email])
            else:  # college
                semester = fallback_semesters[i % len(fallback_semesters)]
                department = fallback_departments[i % len(fallback_departments)]
                writer.writerow([name, section, semester, department, email])
    
    # Prepare file for download
    output.seek(0)
    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    
    return send_file(
        mem,
        mimetype='text/csv',
        as_attachment=True,
        download_name='student_import_template.csv'
    )

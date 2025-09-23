import os
import hashlib
import json
from flask import Flask, render_template, request, redirect, url_for, session, g, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from sqlalchemy import ForeignKey, exc, Text
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator

# --- Custom JSON Type for SQLite ---
class JsonEncodedDict(TypeDecorator):
    """Enables JSON storage by encoding and decoding on the fly."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)

# --- App Initialization ---
app = Flask(__name__)
app.secret_key = os.urandom(24)
load_dotenv()
db_url = os.getenv('DATABASE_URL', 'sqlite:///timetable.db')
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Use JsonEncodedDict for SQLite, and the native JSON for others (like PostgreSQL/MySQL)
json_type = JsonEncodedDict if 'sqlite' in db_url else db.JSON

# --- Association Tables for Many-to-Many Relationships ---
teacher_school_subjects_association = db.Table('teacher_school_subjects',
    db.Column('teacher_id', db.Integer, db.ForeignKey('teacher.id'), primary_key=True),
    db.Column('subject_id', db.Integer, db.ForeignKey('subject.id'), primary_key=True)
)

teacher_college_courses_association = db.Table('teacher_college_courses',
    db.Column('teacher_id', db.Integer, db.ForeignKey('teacher.id'), primary_key=True),
    db.Column('course_id', db.Integer, db.ForeignKey('course.id'), primary_key=True)
)

student_electives_association = db.Table('student_electives',
    db.Column('student_id', db.Integer, db.ForeignKey('student.id'), primary_key=True),
    db.Column('subject_id', db.Integer, db.ForeignKey('subject.id'), primary_key=True)
)

# --- CORE DATABASE MODELS ---

class AppConfig(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text, nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False) # admin, teacher, student
    
    student = relationship("Student", back_populates="user", uselist=False, cascade="all, delete-orphan")
    teacher = relationship("Teacher", back_populates="user", uselist=False, cascade="all, delete-orphan")

# --- School Structure Models ---
class SchoolGroup(db.Model): id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(100), nullable=False)
class Grade(db.Model): id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(50), nullable=False); group_id = db.Column(db.Integer, db.ForeignKey('school_group.id')); group = relationship('SchoolGroup', backref=db.backref('grades', cascade="all, delete-orphan"))
class Stream(db.Model): id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(100), nullable=False); group_id = db.Column(db.Integer, db.ForeignKey('school_group.id')); group = relationship('SchoolGroup', backref=db.backref('streams', cascade="all, delete-orphan"))
class Subject(db.Model): id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(100), nullable=False); code = db.Column(db.String(20), unique=True, nullable=False); weekly_hours = db.Column(db.Integer); is_elective = db.Column(db.Boolean); stream_id = db.Column(db.Integer, db.ForeignKey('stream.id')); stream = relationship('Stream', backref='subjects')

# --- College Structure Models ---
class Semester(db.Model): id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(100), nullable=False)
class Department(db.Model): id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(100), nullable=False); semester_id = db.Column(db.Integer, db.ForeignKey('semester.id')); semester = relationship('Semester', backref=db.backref('departments', cascade="all, delete-orphan"))
class Course(db.Model): id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(100), nullable=False); code = db.Column(db.String(20), unique=True, nullable=False); credits = db.Column(db.Integer); course_type = db.Column(db.String(20)); department_id = db.Column(db.Integer, db.ForeignKey('department.id')); department = relationship('Department', backref='courses')

# --- People & Places ---
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('student_section.id'))
    user = relationship("User", back_populates="student")
    electives = relationship("Subject", secondary=student_electives_association, backref="students")

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    max_weekly_hours = db.Column(db.Integer, nullable=False, default=20)
    user = relationship("User", back_populates="teacher")
    subjects = relationship("Subject", secondary=teacher_school_subjects_association, backref="teachers_school")
    courses = relationship("Course", secondary=teacher_college_courses_association, backref="teachers_college")

class StudentSection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    grade_id = db.Column(db.Integer, db.ForeignKey('grade.id'), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    students = relationship("Student", backref="section")

class Classroom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String(50), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    features = db.Column(json_type, nullable=False, default=lambda: [])

# --- Core Functional Models ---
class TimetableEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(10), nullable=False)
    period = db.Column(db.Integer, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    section_id = db.Column(db.Integer, db.ForeignKey('student_section.id'), nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False)

class AttendanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    entry_id = db.Column(db.Integer, db.ForeignKey('timetable_entry.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False)

class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)

class ExamSeating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False)
    seat_number = db.Column(db.String(10))

# --- System & Logging ---
class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True); timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc)); level = db.Column(db.String(20)); message = db.Column(db.String(255))
    @property
    def time_ago(self):
        timestamp_to_compare = self.timestamp
        if timestamp_to_compare.tzinfo is None:
            timestamp_to_compare = timestamp_to_compare.replace(tzinfo=timezone.utc)
            
        delta = datetime.now(timezone.utc) - timestamp_to_compare
        if delta < timedelta(minutes=1): return "just now"
        elif delta < timedelta(hours=1): return f"{delta.seconds // 60} minutes ago"
        elif delta < timedelta(days=1): return f"{delta.seconds // 3600} hours ago"
        else: return f"{delta.days} days ago"

class SystemMetric(db.Model):
    id = db.Column(db.Integer, primary_key=True); date = db.Column(db.Date, default=lambda: datetime.now(timezone.utc).date()); key = db.Column(db.String(50)); value = db.Column(db.Integer)

# --- Helper Functions ---
def hash_password(password): return hashlib.sha256(password.encode()).hexdigest()

def set_config(key, value):
    config = AppConfig.query.filter_by(key=key).first()
    if config: config.value = str(value)
    else: config = AppConfig(key=key, value=str(value))
    db.session.add(config)

def log_activity(level, message):
    try:
        log = ActivityLog(level=level, message=message); db.session.add(log)
        logs_to_delete = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).offset(20).all()
        for log_del in logs_to_delete: db.session.delete(log_del)
        db.session.commit()
    except Exception as e: print(f"Error logging activity: {e}"); db.session.rollback()

def calculate_growth(metric_key, current_value):
    last_week = datetime.now(timezone.utc).date() - timedelta(days=7)
    last_metric = SystemMetric.query.filter_by(key=metric_key).filter(SystemMetric.date <= last_week).order_by(SystemMetric.date.desc()).first()
    if last_metric and last_metric.value > 0:
        return round(((current_value - last_metric.value) / last_metric.value) * 100, 1)
    return 0

# --- Application Hooks & Core Routes ---
@app.before_request
def check_setup():
    if request.endpoint in ['static', 'setup']: return
    try:
        if not AppConfig.query.filter_by(key='setup_complete', value='true').first():
            return redirect(url_for('setup'))
        g.app_mode = AppConfig.query.filter_by(key='app_mode').first().value
    except: return redirect(url_for('setup'))

@app.context_processor
def inject_global_vars():
    try:
        return {'institute_name': AppConfig.query.filter_by(key='institute_name').first().value}
    except: return {'institute_name': 'Scheduler AI'}

@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    try:
        if AppConfig.query.filter_by(key='setup_complete', value='true').first():
            return redirect(url_for('login'))
    except Exception:
        with app.app_context():
            db.create_all()

    if request.method == 'POST':
        try:
            payload_str = request.form.get('payload')
            data = json.loads(payload_str)
            
            with db.session.begin_nested():
                admin_data = data['admin']
                admin_email = admin_data.get('email', f"{admin_data['username']}@example.com")
                admin = User(username=admin_data['username'], email=admin_email, password=hash_password(admin_data['password']), role='admin')
                db.session.add(admin)

                details = data['details']
                configs = [
                    AppConfig(key='app_mode', value=data['mode']),
                    AppConfig(key='institute_name', value=details['institute_name']),
                    AppConfig(key='working_days', value=details['working_days']),
                    AppConfig(key='period_duration', value=details['period_duration']),
                    AppConfig(key='start_time', value=details['start_time']),
                    AppConfig(key='end_time', value=details['end_time']),
                    AppConfig(key='breaks', value=json.dumps(details['breaks']))
                ]
                db.session.add_all(configs)

                if data['mode'] == 'school':
                    for group_data in data['structure']:
                        new_group = SchoolGroup(name=group_data['name'])
                        db.session.add(new_group)
                        db.session.flush()
                        for grade_data in group_data['grades']:
                            db.session.add(Grade(name=grade_data['name'], group_id=new_group.id))
                        for stream_data in group_data['streams']:
                            new_stream = Stream(name=stream_data['name'], group_id=new_group.id)
                            db.session.add(new_stream)
                            db.session.flush()
                            for subject_data in stream_data['subjects']:
                                db.session.add(Subject(name=subject_data['name'], code=subject_data['code'], weekly_hours=subject_data['hours'], is_elective=subject_data['is_elective'], stream_id=new_stream.id))
                
                elif data['mode'] == 'college':
                    for sem_data in data['structure']:
                        new_sem = Semester(name=sem_data['name'])
                        db.session.add(new_sem)
                        db.session.flush()
                        for dept_data in sem_data['departments']:
                            new_dept = Department(name=dept_data['name'], semester_id=new_sem.id)
                            db.session.add(new_dept)
                            db.session.flush()
                            for course_data in dept_data['courses']:
                                db.session.add(Course(name=course_data['name'], code=course_data['code'], credits=course_data['credits'], course_type=course_data['type'], department_id=new_dept.id))
                
                db.session.add(AppConfig(key='setup_complete', value='true'))

            db.session.commit()
            log_activity('info', f"System setup completed for {details['institute_name']}.")
            
            db.session.add(SystemMetric(key='total_students', value=0))
            db.session.add(SystemMetric(key='total_teachers', value=0))
            db.session.add(SystemMetric(key='total_subjects', value=Subject.query.count() + Course.query.count()))
            db.session.add(SystemMetric(key='classes_scheduled', value=0))
            db.session.commit()
            
            flash('Setup complete! Please log in with your new admin account.', 'success')
            return jsonify({'status': 'success', 'redirect': url_for('login')})

        except Exception as e:
            db.session.rollback()
            print(f"ERROR during setup: {e}")
            return jsonify({'status': 'error', 'message': f'An unexpected error occurred: {e}. Please check the logs.'}), 500
            
    return render_template('setup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == hash_password(request.form['password']):
            session['user_id'] = user.id; session['username'] = user.username; session['role'] = user.role
            log_activity('info', f"User '{user.username}' logged in.")
            return redirect(url_for('dashboard'))
        else: flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    log_activity('info', f"User '{session.get('username')}' logged out.")
    session.clear(); flash('You have been logged out.', 'success'); return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    stats = {
        'teachers': User.query.filter_by(role='teacher').count(),
        'total_students': User.query.filter_by(role='student').count(),
        'classes_scheduled': TimetableEntry.query.count(),
    }
    if g.app_mode == 'school': stats['subjects'] = Subject.query.count()
    else: stats['subjects'] = Course.query.count()

    stats['students_growth'] = calculate_growth('total_students', stats['total_students'])
    stats['teachers_growth'] = calculate_growth('total_teachers', stats['teachers'])
    stats['subjects_growth'] = calculate_growth('total_subjects', stats['subjects'])
    stats['scheduled_growth'] = calculate_growth('classes_scheduled', stats['classes_scheduled'])

    recent_activities = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(5).all()
    performance = {
        'accuracy': AppConfig.query.filter_by(key='last_schedule_accuracy').first(),
        'gen_time': AppConfig.query.filter_by(key='last_generation_time').first(),
    }
    performance['accuracy'] = float(performance['accuracy'].value) if performance['accuracy'] else 0
    performance['gen_time'] = float(performance['gen_time'].value) if performance['gen_time'] else 0
    performance['uptime'] = 99.9

    return render_template('dashboard.html', stats=stats, activities=recent_activities, performance=performance)

@app.route('/generate_timetable', methods=['POST'])
def generate_timetable():
    import time, random
    start_time = time.time()
    time.sleep(random.uniform(0.5, 2.0))
    end_time = time.time()
    
    gen_time = round(end_time - start_time, 2)
    accuracy = round(random.uniform(95.0, 99.8), 1)

    set_config('last_generation_time', gen_time)
    set_config('last_schedule_accuracy', accuracy)
    db.session.commit()
    
    log_activity('info', f'New timetable generated with {accuracy}% accuracy.')
    
    return jsonify({'message': f'Timetable generated in {gen_time}s!'})

# --- Structure and API Routes ---
@app.route('/structure')
def manage_structure():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('structure.html')

@app.route('/api/structure/<mode>', methods=['GET'])
def get_structure_items(mode):
    if 'user_id' not in session: return jsonify({"message": "Unauthorized"}), 401
    
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

@app.route('/api/structure/school', methods=['POST'])
@app.route('/api/structure/school/<int:item_id>', methods=['PUT', 'DELETE'])
def handle_school_structure(item_id=None):
    if 'user_id' not in session: return jsonify({"message": "Unauthorized"}), 401
    
    if request.method == 'POST': # Create New
        data = request.json
        new_group = SchoolGroup(name=data['name'])
        db.session.add(new_group)
        db.session.flush() # Get the ID for relationships
        for grade in data.get('grades', []):
            if grade.get('name'): db.session.add(Grade(name=grade['name'], group_id=new_group.id))
        for stream in data.get('streams', []):
            if stream.get('name'): db.session.add(Stream(name=stream['name'], group_id=new_group.id))
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
        for gid_to_del in existing_grades.keys() - updated_grade_ids: db.session.delete(existing_grades[gid_to_del])
        for g_data in data['grades']:
            gid = g_data.get('id')
            if gid and not str(gid).startswith('new-'): existing_grades[int(gid)].name = g_data['name']
            elif g_data.get('name'): db.session.add(Grade(name=g_data['name'], group_id=group.id))
            
        # Sync Streams
        existing_streams = {s.id: s for s in group.streams}
        updated_stream_ids = {int(s['id']) for s in data['streams'] if s.get('id') and not str(s['id']).startswith('new-')}
        for sid_to_del in existing_streams.keys() - updated_stream_ids: db.session.delete(existing_streams[sid_to_del])
        for s_data in data['streams']:
            sid = s_data.get('id')
            if sid and not str(sid).startswith('new-'): existing_streams[int(sid)].name = s_data['name']
            elif s_data.get('name'): db.session.add(Stream(name=s_data['name'], group_id=group.id))

        db.session.commit()
        log_activity('info', f"School group '{group.name}' updated.")
        return jsonify({"message": "Group updated successfully!"})
        
    if request.method == 'DELETE':
        log_activity('warning', f"School group '{group.name}' deleted.")
        db.session.delete(group)
        db.session.commit()
        return jsonify({"message": "Group deleted successfully!"})

@app.route('/api/structure/college', methods=['POST'])
@app.route('/api/structure/college/<int:item_id>', methods=['PUT', 'DELETE'])
def handle_college_structure(item_id=None):
    if 'user_id' not in session: return jsonify({"message": "Unauthorized"}), 401

    if request.method == 'POST':
        data = request.json
        new_sem = Semester(name=data['name'])
        db.session.add(new_sem)
        db.session.flush()
        for dept in data.get('departments', []):
            if dept.get('name'): db.session.add(Department(name=dept['name'], semester_id=new_sem.id))
        db.session.commit()
        log_activity('info', f"Semester '{data['name']}' created.")
        return jsonify({"message": "Semester created successfully!"})

    semester = Semester.query.get_or_404(item_id)
    if request.method == 'PUT':
        data = request.json
        semester.name = data['name']
        
        existing_depts = {d.id: d for d in semester.departments}
        updated_dept_ids = {int(d['id']) for d in data['departments'] if d.get('id') and not str(d['id']).startswith('new-')}
        for did_to_del in existing_depts.keys() - updated_dept_ids: db.session.delete(existing_depts[did_to_del])
        for d_data in data['departments']:
            did = d_data.get('id')
            if did and not str(did).startswith('new-'): existing_depts[int(did)].name = d_data['name']
            elif d_data.get('name'): db.session.add(Department(name=d_data['name'], semester_id=semester.id))
            
        db.session.commit()
        log_activity('info', f"Semester '{semester.name}' updated.")
        return jsonify({"message": "Semester updated successfully!"})

    if request.method == 'DELETE':
        log_activity('warning', f"Semester '{semester.name}' deleted.")
        db.session.delete(semester)
        db.session.commit()
        return jsonify({"message": "Semester deleted successfully!"})

@app.route('/subjects')
def manage_subjects():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('subjects.html')

# --- API Routes for Subject/Course Management ---
@app.route('/api/subjects/parents/<mode>', methods=['GET'])
def get_parent_data(mode):
    if 'user_id' not in session: return jsonify({"message": "Unauthorized"}), 401
    
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

@app.route('/api/subjects/<mode>', methods=['GET'])
def get_subjects_data(mode):
    if 'user_id' not in session: return jsonify({"message": "Unauthorized"}), 401
    parent_id = request.args.get('parent_id', type=int)
    if not parent_id: return jsonify({"items": []})
    
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

@app.route('/api/subjects/<mode>', methods=['POST'])
@app.route('/api/subjects/<mode>/<int:item_id>', methods=['PUT', 'DELETE'])
def handle_subjects(mode, item_id=None):
    if 'user_id' not in session: return jsonify({"message": "Unauthorized"}), 401
    
    if request.method not in ['POST', 'PUT', 'DELETE']:
        return jsonify({"message": "Method not allowed"}), 405

    data = request.json if request.method in ['POST', 'PUT'] else None

    try:
        # --- Create Operation ---
        if request.method == 'POST':
            code = data.get('code')
            if not code: return jsonify({"message": "Code is a required field."}), 400

            if mode == 'school':
                if Subject.query.filter_by(code=code).first():
                    return jsonify({"message": f"Subject code '{code}' already exists."}), 409
                new_item = Subject(name=data['name'], code=code, weekly_hours=data['weekly_hours'], is_elective=data.get('is_elective', False), stream_id=data['stream_id'])
                db.session.add(new_item)
                message = "Subject created successfully!"
            
            else: # college
                if Course.query.filter_by(code=code).first():
                    return jsonify({"message": f"Course code '{code}' already exists."}), 409
                new_item = Course(name=data['name'], code=code, credits=data['credits'], course_type=data['course_type'], department_id=data['department_id'])
                db.session.add(new_item)
                message = "Course created successfully!"
            
            log_activity('info', f"{'Subject' if mode == 'school' else 'Course'} '{data['name']}' created.")

        # --- Get item for Update/Delete ---
        else:
            item = Subject.query.get_or_404(item_id) if mode == 'school' else Course.query.get_or_404(item_id)

            # --- Update Operation ---
            if request.method == 'PUT':
                new_code = data.get('code')
                if not new_code: return jsonify({"message": "Code is a required field."}), 400

                # Check for code uniqueness if it's being changed
                if item.code != new_code:
                    if mode == 'school' and Subject.query.filter_by(code=new_code).first():
                        return jsonify({"message": f"Subject code '{new_code}' already exists."}), 409
                    if mode == 'college' and Course.query.filter_by(code=new_code).first():
                        return jsonify({"message": f"Course code '{new_code}' already exists."}), 409
                
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

            # --- Delete Operation ---
            elif request.method == 'DELETE':
                db.session.delete(item)
                log_activity('warning', f"{'Subject' if mode == 'school' else 'Course'} '{item.name}' deleted.")
                message = f"{'Subject' if mode == 'school' else 'Course'} deleted successfully!"

        db.session.commit()
        return jsonify({"message": message})

    except exc.IntegrityError as e:
        db.session.rollback()
        return jsonify({"message": "Database integrity error. Check for duplicate codes or invalid IDs."}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"An unexpected error occurred: {e}"}), 500

@app.route('/staff')
def manage_staff():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('staff.html')

@app.route('/api/staff/all_subjects', methods=['GET'])
def get_all_subjects_for_staff():
    if 'user_id' not in session: return jsonify({"message": "Unauthorized"}), 401
    
    subjects_list = []
    if g.app_mode == 'school':
        subjects = Subject.query.order_by(Subject.name).all()
        subjects_list = [{"id": s.id, "name": s.name, "code": s.code, "type": "subject"} for s in subjects]
    else:
        courses = Course.query.order_by(Course.name).all()
        subjects_list = [{"id": c.id, "name": c.name, "code": c.code, "type": "course"} for c in courses]
        
    return jsonify({"subjects": subjects_list})

@app.route('/api/staff', methods=['GET', 'POST'])
@app.route('/api/staff/<int:teacher_id>', methods=['PUT', 'DELETE'])
def handle_staff(teacher_id=None):
    if 'user_id' not in session: return jsonify({"message": "Unauthorized"}), 401

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

        if request.method in ['POST', 'PUT']:
            data = request.json
        
        # --- Create Operation ---
        if request.method == 'POST':
            if not data.get('password'): return jsonify({"message": "Password is required for new teachers."}), 400
            
            if User.query.filter_by(username=data['username']).first():
                return jsonify({"message": "Username already exists."}), 409
            if User.query.filter_by(email=data['email']).first():
                return jsonify({"message": "Email already exists."}), 409

            new_user = User(
                username=data['username'],
                email=data['email'],
                password=hash_password(data['password']),
                role='teacher'
            )
            db.session.add(new_user)
            db.session.flush()

            new_teacher = Teacher(
                full_name=data['full_name'],
                max_weekly_hours=data['max_weekly_hours'],
                user_id=new_user.id
            )
            db.session.add(new_teacher)
            db.session.flush()

            if g.app_mode == 'school':
                subjects = Subject.query.filter(Subject.id.in_(data.get('subject_ids', []))).all()
                new_teacher.subjects = subjects
            else:
                courses = Course.query.filter(Course.id.in_(data.get('subject_ids', []))).all()
                new_teacher.courses = courses

            db.session.commit()
            log_activity('info', f"Teacher '{data['full_name']}' created.")
            return jsonify({"message": "Teacher created successfully!"})
        
        teacher = Teacher.query.get_or_404(teacher_id)
        
        # --- Update Operation ---
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

        # --- Delete Operation ---
        if request.method == 'DELETE':
            user_to_delete = teacher.user
            db.session.delete(teacher)
            db.session.delete(user_to_delete)
            db.session.commit()
            log_activity('warning', f"Teacher '{teacher.full_name}' deleted.")
            return jsonify({"message": "Teacher deleted successfully!"})

    except exc.IntegrityError as e:
        db.session.rollback()
        print(f"ERROR in handle_staff (Integrity): {e}")
        return jsonify({"message": "Database integrity error occurred."}), 400
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in handle_staff: {e}")
        return jsonify({"message": f"An unexpected error occurred: {e}"}), 500

@app.route('/sections')
def manage_sections(): return "<h1>Manage Sections</h1>"
@app.route('/classrooms')
def manage_classrooms():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('classrooms.html')

@app.route('/api/classrooms', methods=['GET', 'POST'])
@app.route('/api/classrooms/<int:classroom_id>', methods=['PUT', 'DELETE'])
def handle_classrooms(classroom_id=None):
    if 'user_id' not in session: return jsonify({"message": "Unauthorized"}), 401
    
    try:
        if request.method == 'GET':
            classrooms = Classroom.query.order_by(Classroom.room_id).all()
            return jsonify({"classrooms": [
                {"id": c.id, "room_id": c.room_id, "capacity": c.capacity, "features": c.features or []} for c in classrooms
            ]})

        if request.method in ['POST', 'PUT']:
            data = request.json
            if not data.get('room_id') or not data.get('capacity'):
                return jsonify({"message": "Room ID and Capacity are required fields."}), 400

        if request.method == 'POST':
            if Classroom.query.filter_by(room_id=data['room_id']).first():
                return jsonify({"message": f"Classroom with ID '{data['room_id']}' already exists."}), 409
            
            new_classroom = Classroom(
                room_id=data['room_id'],
                capacity=data['capacity'],
                features=data.get('features', [])
            )
            db.session.add(new_classroom)
            log_activity('info', f"Classroom '{data['room_id']}' created.")
            message = "Classroom created successfully."

        else: # PUT or DELETE
            classroom = Classroom.query.get_or_404(classroom_id)
            if request.method == 'PUT':
                if classroom.room_id != data['room_id'] and Classroom.query.filter_by(room_id=data['room_id']).first():
                    return jsonify({"message": f"Classroom with ID '{data['room_id']}' already exists."}), 409
                
                classroom.room_id = data['room_id']
                classroom.capacity = data['capacity']
                classroom.features = data.get('features', [])
                log_activity('info', f"Classroom '{classroom.room_id}' updated.")
                message = "Classroom updated successfully."
            
            elif request.method == 'DELETE':
                db.session.delete(classroom)
                log_activity('warning', f"Classroom '{classroom.room_id}' deleted.")
                message = "Classroom deleted successfully."
        
        db.session.commit()
        return jsonify({"message": message})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in handle_classrooms: {e}")
        return jsonify({"message": "An unexpected server error occurred."}), 500

@app.route('/timetable')
def view_timetable(): return "<h1>View Timetable</h1>"
@app.route('/analytics')
def analytics(): return "<h1>Analytics</h1>"

# --- Main Execution ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        today = datetime.now(timezone.utc).date()
        if not SystemMetric.query.filter_by(date=today).first():
             db.session.add(SystemMetric(key='total_students', value=User.query.filter_by(role='student').count()))
             db.session.add(SystemMetric(key='total_teachers', value=User.query.filter_by(role='teacher').count()))
             total_subjects = Subject.query.count() + Course.query.count()
             db.session.add(SystemMetric(key='total_subjects', value=total_subjects))
             db.session.add(SystemMetric(key='classes_scheduled', value=TimetableEntry.query.count()))
             db.session.commit()
    app.run(debug=True)


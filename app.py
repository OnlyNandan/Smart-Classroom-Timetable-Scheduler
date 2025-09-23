import os
import hashlib
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from dotenv import load_dotenv

# App initialization
app = Flask(__name__)
app.secret_key = os.urandom(24)
load_dotenv()
database_url = os.getenv('DATABASE_URL', 'sqlite:///timetable.db')

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Association Tables ---
teacher_grades = db.Table('teacher_grades',
    db.Column('teacher_id', db.String(20), db.ForeignKey('teacher.teacher_id'), primary_key=True),
    db.Column('grade_id', db.Integer, db.ForeignKey('grade.id'), primary_key=True)
)
teacher_courses = db.Table('teacher_courses',
    db.Column('teacher_id', db.String(20), db.ForeignKey('teacher.teacher_id'), primary_key=True),
    db.Column('course_id', db.String(20), db.ForeignKey('course.course_id'), primary_key=True)
)

# --- Main Models ---
class AppConfig(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(100), nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='teacher')

class Grade(db.Model): # Represents Grade for School, Semester for College
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    is_static_classroom = db.Column(db.Boolean, default=False)

class Course(db.Model):
    course_id = db.Column(db.String(20), primary_key=True)
    course_name = db.Column(db.String(100), nullable=False)
    weekly_hours = db.Column(db.Integer, nullable=False)
    grade_id = db.Column(db.Integer, db.ForeignKey('grade.id'), nullable=False)
    grade = db.relationship('Grade', backref=db.backref('courses', lazy=True))

class Teacher(db.Model):
    teacher_id = db.Column(db.String(20), primary_key=True)
    teacher_name = db.Column(db.String(100), nullable=False)
    max_hours_week = db.Column(db.Integer, nullable=False)
    grades = db.relationship('Grade', secondary=teacher_grades, lazy='subquery', backref=db.backref('teachers', lazy=True))
    courses = db.relationship('Course', secondary=teacher_courses, lazy='subquery', backref=db.backref('teachers', lazy=True))

class Classroom(db.Model):
    room_id = db.Column(db.String(20), primary_key=True)
    type = db.Column(db.String(20), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)

class StudentSection(db.Model): # Represents Section for School, Branch/Batch for College
    section_id = db.Column(db.String(20), primary_key=True)
    no_of_students = db.Column(db.Integer, nullable=False)
    grade_id = db.Column(db.Integer, db.ForeignKey('grade.id'), nullable=False)
    assigned_classroom_id = db.Column(db.String(20), db.ForeignKey('classroom.room_id'), nullable=True)
    grade = db.relationship('Grade', backref=db.backref('sections', lazy=True))
    classroom = db.relationship('Classroom', backref=db.backref('assigned_sections', lazy=True))

class TimetableEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(10), nullable=False)
    time_slot = db.Column(db.String(20), nullable=False)
    course_id = db.Column(db.String(20), db.ForeignKey('course.course_id'), nullable=False)
    teacher_id = db.Column(db.String(20), db.ForeignKey('teacher.teacher_id'), nullable=False)
    classroom_id = db.Column(db.String(20), db.ForeignKey('classroom.room_id'), nullable=False)
    section_id = db.Column(db.String(20), db.ForeignKey('student_section.section_id'), nullable=False)
    course = db.relationship('Course', backref=db.backref('timetable_entries', lazy=True))
    teacher = db.relationship('Teacher', backref=db.backref('timetable_entries', lazy=True))
    classroom = db.relationship('Classroom', backref=db.backref('timetable_entries', lazy=True))
    section = db.relationship('StudentSection', backref=db.backref('timetable_entries', lazy=True))

# --- Helper Functions ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def is_admin():
    return 'role' in session and session['role'] == 'admin'

# --- Hooks and Core Routes ---
@app.before_request
def before_request_func():
    try:
        # Make sure tables exist before querying
        with app.app_context():
            db.create_all()
        config_mode = AppConfig.query.filter_by(key='app_mode').first()
        g.app_mode = config_mode.value if config_mode else None
        
        if not g.app_mode and request.endpoint not in ['setup', 'static', 'logout', 'login']:
             if is_admin():
                return redirect(url_for('setup'))
    except Exception as e:
        # This can happen if the database URL is not yet configured or tables dont exist
        g.app_mode = None
        print(f"Database connection check failed: {e}")


@app.context_processor
def inject_app_mode():
    return dict(app_mode=getattr(g, 'app_mode', None))

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if not is_admin(): return redirect(url_for('login'))
    if getattr(g, 'app_mode', None) and request.method == 'GET':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        mode = request.form.get('mode')
        if mode in ['school', 'college']:
            from init_db import clear_data, create_school_data
            
            clear_data()
            if mode == 'school':
                create_school_data()
            # In the future, you would add:
            # elif mode == 'college':
            #    create_college_data()
            
            # Re-check mode to avoid redirect loop
            config_mode = AppConfig.query.filter_by(key='app_mode').first()
            g.app_mode = config_mode.value if config_mode else None

            return redirect(url_for('dashboard'))
    return render_template('setup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pass = hash_password(password)
        user = User.query.filter_by(username=username, password=hashed_pass).first()
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    if not g.app_mode: return redirect(url_for('setup'))

    if session['role'] == 'admin':
        stats = {
            'total_levels': Grade.query.count(),
            'total_courses': Course.query.count(),
            'total_teachers': Teacher.query.count(),
            'total_classrooms': Classroom.query.count(),
            'total_sections': StudentSection.query.count(),
        }
        return render_template('dashboard.html', **stats)
    else:
        teacher = Teacher.query.filter_by(teacher_name=session['username']).first()
        timetable = TimetableEntry.query.filter_by(teacher_id=teacher.teacher_id).all() if teacher else []
        return render_template('teacher_dashboard.html', timetable=timetable)

@app.route('/levels', methods=['GET', 'POST']) # Renamed from /grades
def manage_levels():
    if not is_admin(): return redirect(url_for('login'))
    if request.method == 'POST':
        grade_name = request.form['name']
        is_static = 'is_static_classroom' in request.form
        new_grade = Grade(name=grade_name, is_static_classroom=is_static)
        db.session.add(new_grade)
        db.session.commit()
        return redirect(url_for('manage_levels'))
    grades = Grade.query.all()
    return render_template('levels.html', levels=grades)

@app.route('/courses', methods=['GET', 'POST'])
def manage_courses():
    if not is_admin(): return redirect(url_for('login'))
    if request.method == 'POST':
        new_course = Course(
            course_id=request.form['course_id'], course_name=request.form['course_name'],
            weekly_hours=int(request.form['weekly_hours']), grade_id=int(request.form['grade_id'])
        )
        db.session.add(new_course)
        db.session.commit()
        return redirect(url_for('manage_courses'))
    return render_template('courses.html', courses=Course.query.all(), grades=Grade.query.all())

@app.route('/teachers', methods=['GET', 'POST'])
def manage_teachers():
    if not is_admin(): return redirect(url_for('login'))
    if request.method == 'POST':
        teacher = Teacher(
            teacher_id=request.form['teacher_id'], teacher_name=request.form['teacher_name'],
            max_hours_week=int(request.form['max_hours_week'])
        )
        grade_ids = request.form.getlist('grades')
        course_ids = request.form.getlist('courses')
        teacher.grades = Grade.query.filter(Grade.id.in_(grade_ids)).all()
        teacher.courses = Course.query.filter(Course.course_id.in_(course_ids)).all()
        db.session.add(teacher)
        db.session.commit()
        return redirect(url_for('manage_teachers'))
    return render_template('teachers.html', teachers=Teacher.query.all(), grades=Grade.query.all(), courses=Course.query.all())

@app.route('/classrooms', methods=['GET', 'POST'])
def manage_classrooms():
    if not is_admin(): return redirect(url_for('login'))
    if request.method == 'POST':
        new_classroom = Classroom(
            room_id=request.form['room_id'], type=request.form['type'], capacity=int(request.form['capacity'])
        )
        db.session.add(new_classroom)
        db.session.commit()
        return redirect(url_for('manage_classrooms'))
    return render_template('classrooms.html', classrooms=Classroom.query.all())

@app.route('/student_sections', methods=['GET', 'POST'])
def manage_student_sections():
    if not is_admin(): return redirect(url_for('login'))
    if request.method == 'POST':
        new_section = StudentSection(
            section_id=request.form['section_id'], no_of_students=int(request.form['no_of_students']),
            grade_id=int(request.form['grade_id']), assigned_classroom_id=request.form.get('assigned_classroom_id') or None
        )
        db.session.add(new_section)
        db.session.commit()
        return redirect(url_for('manage_student_sections'))
    return render_template('student_sections.html', sections=StudentSection.query.all(), grades=Grade.query.all(), classrooms=Classroom.query.all())

@app.route('/timetable')
def view_timetable():
    if 'user_id' not in session: return redirect(url_for('login'))
    entries = TimetableEntry.query.all()
    grid = {}
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    time_slots = sorted(list(set(e.time_slot for e in entries)))

    for day in days:
        grid[day] = {slot: [] for slot in time_slots}
    for entry in entries:
        if entry.day in grid and entry.time_slot in grid[entry.day]:
            grid[entry.day][entry.time_slot].append({
                "course": entry.course.course_name,
                "teacher": entry.teacher.teacher_name,
                "room": entry.classroom.room_id,
                "section": entry.section.section_id
            })
    return render_template('timetable.html', timetable_grid=grid, days=days, time_slots=time_slots)

@app.route('/analytics')
def analytics():
    if not is_admin(): return redirect(url_for('login'))
    # Placeholder for future analytics logic
    return render_template('analytics.html', room_utilization={}, faculty_workload={})

@app.route('/generate_timetable', methods=['POST'])
def generate_timetable():
    if not is_admin(): return jsonify({"error": "Unauthorized"}), 403
    # Placeholder for future GA logic
    return jsonify({"error": "Timetable generation is not yet adapted for the new data model."}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)


import os
import hashlib
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

# App initialization
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:secretpassword@localhost/timetabledb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Database Models ---
from genetic_algorithm import run_genetic_algorithm

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='teacher') 

    def __repr__(self):
        return f'<User {self.username}>'

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    credit_hours = db.Column(db.Integer, nullable=False)
    lab_required = db.Column(db.Boolean, default=False)

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100))
    # A teacher can teach multiple subjects. We will manage this relationship separately if needed.

class Classroom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(20), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    has_projector = db.Column(db.Boolean, default=False)
    is_lab = db.Column(db.Boolean, default=False)

class StudentGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class TimetableEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(10), nullable=False) 
    time_slot = db.Column(db.String(20), nullable=False) 
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False)
    student_group_id = db.Column(db.Integer, db.ForeignKey('student_group.id'), nullable=False)

    course = db.relationship('Course', backref=db.backref('timetable_entries', lazy=True))
    teacher = db.relationship('Teacher', backref=db.backref('timetable_entries', lazy=True))
    classroom = db.relationship('Classroom', backref=db.backref('timetable_entries', lazy=True))
    student_group = db.relationship('StudentGroup', backref=db.backref('timetable_entries', lazy=True))


# --- Helper Functions ---
def hash_password(password):
    """Hashes a password for storing."""
    return hashlib.sha256(password.encode()).hexdigest()

# --- Routes ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

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
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['role'] == 'admin':
        total_courses = Course.query.count()
        total_teachers = Teacher.query.count()
        total_classrooms = Classroom.query.count()
        total_student_groups = StudentGroup.query.count()
        
        return render_template('dashboard.html', 
                                total_courses=total_courses,
                                total_teachers=total_teachers,
                                total_classrooms=total_classrooms,
                                total_student_groups=total_student_groups)
    else:
        teacher_id = Teacher.query.filter_by(name=session['username']).first().id # Simplified assumption
        timetable = TimetableEntry.query.filter_by(teacher_id=teacher_id).all()
        return render_template('teacher_dashboard.html', timetable=timetable)


# --- CRUD Routes for Master Data (Admin only) ---

def is_admin():
    return 'role' in session and session['role'] == 'admin'

@app.route('/courses', methods=['GET', 'POST'])
def manage_courses():
    if not is_admin(): return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name']
        code = request.form['code']
        credit_hours = request.form['credit_hours']
        lab_required = 'lab_required' in request.form
        new_course = Course(name=name, code=code, credit_hours=credit_hours, lab_required=lab_required)
        db.session.add(new_course)
        db.session.commit()
        return redirect(url_for('manage_courses'))
    
    courses = Course.query.all()
    return render_template('courses.html', courses=courses)

@app.route('/teachers', methods=['GET', 'POST'])
def manage_teachers():
    if not is_admin(): return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name']
        contact = request.form['contact']
        new_teacher = Teacher(name=name, contact=contact)
        db.session.add(new_teacher)
        db.session.commit()
        return redirect(url_for('manage_teachers'))
        
    teachers = Teacher.query.all()
    return render_template('teachers.html', teachers=teachers)

@app.route('/classrooms', methods=['GET', 'POST'])
def manage_classrooms():
    if not is_admin(): return redirect(url_for('login'))
    if request.method == 'POST':
        room_number = request.form['room_number']
        capacity = request.form['capacity']
        has_projector = 'has_projector' in request.form
        is_lab = 'is_lab' in request.form
        new_classroom = Classroom(room_number=room_number, capacity=capacity, has_projector=has_projector, is_lab=is_lab)
        db.session.add(new_classroom)
        db.session.commit()
        return redirect(url_for('manage_classrooms'))

    classrooms = Classroom.query.all()
    return render_template('classrooms.html', classrooms=classrooms)

@app.route('/student_groups', methods=['GET', 'POST'])
def manage_student_groups():
    if not is_admin(): return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name']
        new_group = StudentGroup(name=name)
        db.session.add(new_group)
        db.session.commit()
        return redirect(url_for('manage_student_groups'))

    groups = StudentGroup.query.all()
    return render_template('student_groups.html', groups=groups)


# Timetable Generation Placeholder
@app.route('/generate_timetable', methods=['POST'])
def generate_timetable():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        print("Starting timetable generation...")
        courses = Course.query.all()
        teachers = Teacher.query.all()
        classrooms = Classroom.query.all()
        student_groups = StudentGroup.query.all()
        
        # Define constraints (can be expanded)
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        time_slots = ["09:00-10:30", "10:30-12:00", "13:00-14:30", "14:30-16:00"]

        # 2. Run the Genetic Algorithm
        # This can take time. In a production app, use a background task runner like Celery.
        best_timetable_df = run_genetic_algorithm(
            courses=courses,
            teachers=teachers,
            rooms=classrooms,
            groups=student_groups,
            days=days,
            time_slots=time_slots,
            population_size=100,
            generations=50
        )

        if best_timetable_df is None or best_timetable_df.empty:
            return jsonify({"error": "Could not generate a valid timetable. Check constraints."}), 500

        print("Saving generated timetable to the database...")
        db.session.query(TimetableEntry).delete()
        
        for index, row in best_timetable_df.iterrows():
            entry = TimetableEntry(
                day=row['day'],
                time_slot=row['time_slot'],
                course_id=row['course_id'],
                teacher_id=row['teacher_id'],
                classroom_id=row['room_id'],
                student_group_id=row['group_id']
            )
            db.session.add(entry)
            
        db.session.commit()
        print("Timetable saved successfully.")
        
        return jsonify({"message": f"Timetable generated and saved successfully! {len(best_timetable_df)} classes scheduled."})

    except Exception as e:
        db.session.rollback()
        print(f"Error during timetable generation: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/timetable')
def view_timetable():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    timetable_entries = TimetableEntry.query.all()
    
    timetable_grid = {}
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    time_slots = sorted(list(set(entry.time_slot for entry in timetable_entries)))

    for day in days:
        timetable_grid[day] = {}
        for slot in time_slots:
            timetable_grid[day][slot] = []

    for entry in timetable_entries:
        if entry.day in timetable_grid and entry.time_slot in timetable_grid[entry.day]:
            timetable_grid[entry.day][entry.time_slot].append({
                "course": entry.course.name,
                "teacher": entry.teacher.name,
                "room": entry.classroom.room_number,
                "group": entry.student_group.name
            })
            
    return render_template('timetable.html', timetable_grid=timetable_grid, days=days, time_slots=time_slots)


@app.route('/analytics')
def analytics():
    if not is_admin(): return redirect(url_for('login'))
    room_utilization = {"Room A": 75, "Room B": 50, "Lab 1": 90}
    faculty_workload = {"Teacher X": 18, "Teacher Y": 15}
    return render_template('analytics.html', room_utilization=room_utilization, faculty_workload=faculty_workload)


def create_db():
    """Creates database and tables if they don't exist."""
    with app.app_context():
        db.create_all()

        # Create a default admin user if one doesn't exist
        if not User.query.filter_by(username='admin').first():
            print("Creating default admin user...")
            admin_user = User(
                username='admin',
                password=hash_password('admin'),
                role='admin'
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created with username 'admin' and password 'admin'")


if __name__ == '__main__':
    create_db()
    app.run(debug=True)


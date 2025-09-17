import os
import hashlib
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

# App initialization
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Database configuration
database_url = os.getenv('DATABASE_URL', '').strip()
if not database_url:
    database_url = 'sqlite:///timetable.db'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
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


# 1. Courses
class Course(db.Model):
    course_id = db.Column(db.String(20), primary_key=True)   # e.g., CSE301
    course_name = db.Column(db.String(100), nullable=False)  # e.g., Data Structures
    weekly_hours = db.Column(db.Integer, nullable=False)
    reqd_lab = db.Column(db.Boolean, default=False)
    lab_hours = db.Column(db.Integer, default=0)


# 2. Teachers
class Teacher(db.Model):
    teacher_id = db.Column(db.String(20), primary_key=True)
    teacher_name = db.Column(db.String(100), nullable=False)
    handling_subject = db.Column(db.String(20), db.ForeignKey('course.course_id'))
    max_hours_week = db.Column(db.Integer, nullable=False)

    course = db.relationship('Course', backref=db.backref('teachers', lazy=True))


# 3. Classrooms
class Classroom(db.Model):
    room_id = db.Column(db.String(20), primary_key=True)
    type = db.Column(db.String(20), nullable=False)  # Classroom / Lab
    capacity = db.Column(db.Integer, nullable=False)


# 4. Student Groups
class StudentGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)


# 5. Student Sections
class StudentSection(db.Model):
    section_id = db.Column(db.String(20), primary_key=True)
    no_of_students = db.Column(db.Integer, nullable=False)
    assigned_classroom = db.Column(db.String(20), db.ForeignKey('classroom.room_id'))

    classroom = db.relationship('Classroom', backref=db.backref('sections', lazy=True))


# --- Course–Teacher Mapping (fixed names) ---
class CourseTeacherMapping(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.String(20), db.ForeignKey('course.course_id'), nullable=False)
    teacher_id = db.Column(db.String(20), db.ForeignKey('teacher.teacher_id'), nullable=False)
    sec_id = db.Column(db.String(20), db.ForeignKey('student_section.section_id'), nullable=False)

    course = db.relationship('Course', backref=db.backref('course_teacher_mappings', lazy=True))
    teacher = db.relationship('Teacher', backref=db.backref('course_teacher_mappings', lazy=True))
    section = db.relationship('StudentSection', backref=db.backref('course_teacher_mappings', lazy=True))



# Timetable Entry (uses StudentGroup)
# Timetable Entry (now uses StudentSection)
class TimetableEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(10), nullable=False) 
    time_slot = db.Column(db.String(20), nullable=False) 
    course_id = db.Column(db.String(20), db.ForeignKey('course.course_id'), nullable=False)
    teacher_id = db.Column(db.String(20), db.ForeignKey('teacher.teacher_id'), nullable=False)
    classroom_id = db.Column(db.String(20), db.ForeignKey('classroom.room_id'), nullable=False)
    section_id = db.Column(db.String(20), db.ForeignKey('student_section.section_id'), nullable=False)  # ✅ changed

    course = db.relationship('Course', backref=db.backref('timetable_entries', lazy=True))
    teacher = db.relationship('Teacher', backref=db.backref('timetable_entries', lazy=True))
    classroom = db.relationship('Classroom', backref=db.backref('timetable_entries', lazy=True))
    section = db.relationship('StudentSection', backref=db.backref('timetable_entries', lazy=True))  # ✅ changed


    def __repr__(self):
        return f"<TimetableEntry {self.day} {self.time_slot} {self.course_id} {self.section_id}>"


# --- Helper Functions ---
def hash_password(password):
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
        total_student_sections = StudentSection.query.count()
        
        return render_template('dashboard.html', 
                                total_courses=total_courses,
                                total_teachers=total_teachers,
                                total_classrooms=total_classrooms,
                                total_student_sections=total_student_sections)
    else:
        teacher = Teacher.query.filter_by(teacher_name=session['username']).first()
        if not teacher:
            return render_template('teacher_dashboard.html', timetable=[])
        timetable = TimetableEntry.query.filter_by(teacher_id=teacher.teacher_id).all()
        return render_template('teacher_dashboard.html', timetable=timetable)


# --- CRUD Routes (Admin only) ---

def is_admin():
    return 'role' in session and session['role'] == 'admin'

@app.route('/courses', methods=['GET', 'POST'])
def manage_courses():
    if not is_admin(): return redirect(url_for('login'))
    if request.method == 'POST':
        course_id = request.form['course_id']
        course_name = request.form['course_name']
        weekly_hours = int(request.form['weekly_hours'])
        reqd_lab = 'reqd_lab' in request.form
        lab_hours = int(request.form['lab_hours']) if reqd_lab else 0

        new_course = Course(
            course_id=course_id,
            course_name=course_name,
            weekly_hours=weekly_hours,
            reqd_lab=reqd_lab,
            lab_hours=lab_hours
        )
        db.session.add(new_course)
        db.session.commit()
        return redirect(url_for('manage_courses'))
    
    courses = Course.query.all()
    return render_template('courses.html', courses=courses)


@app.route('/teachers', methods=['GET', 'POST'])
def manage_teachers():
    if not is_admin(): 
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        teacher_id = request.form['teacher_id']
        teacher_name = request.form['teacher_name']
        handling_subject = request.form['handling_subject']   # course_id
        max_hours_week = int(request.form['max_hours_week'])

        new_teacher = Teacher(
            teacher_id=teacher_id,
            teacher_name=teacher_name,
            handling_subject=handling_subject,
            max_hours_week=max_hours_week
        )
        db.session.add(new_teacher)
        db.session.commit()
        return redirect(url_for('manage_teachers'))
    
    teachers = Teacher.query.all()
    courses = Course.query.all()   # to populate subject dropdown
    return render_template('teachers.html', teachers=teachers, courses=courses)

@app.route('/classrooms', methods=['GET', 'POST'])
def manage_classrooms():
    if not is_admin(): 
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        room_id = request.form['room_id']
        room_type = request.form['type']   # "Classroom" / "Lab"
        capacity = int(request.form['capacity'])

        new_classroom = Classroom(
            room_id=room_id,
            type=room_type,
            capacity=capacity
        )
        db.session.add(new_classroom)
        db.session.commit()
        return redirect(url_for('manage_classrooms'))
    
    classrooms = Classroom.query.all()
    return render_template('classrooms.html', classrooms=classrooms)

@app.route('/student_sections', methods=['GET', 'POST'])
def manage_student_sections():
    if not is_admin(): 
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        section_id = request.form['section_id']
        no_of_students = int(request.form['no_of_students'])
        assigned_classroom = request.form['assigned_classroom']

        new_section = StudentSection(
            section_id=section_id,
            no_of_students=no_of_students,
            assigned_classroom=assigned_classroom
        )
        db.session.add(new_section)
        db.session.commit()
        return redirect(url_for('manage_student_sections'))
    
    sections = StudentSection.query.all()
    classrooms = Classroom.query.all()
    return render_template(
        'student_sections.html',
        sections=sections,
        classrooms=classrooms
    )


@app.route('/course_teacher_mapping', methods=['GET', 'POST'])
def manage_course_teacher_mapping():
    if not is_admin(): 
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        course_id = request.form.get('course_id')
        teacher_id = request.form.get('teacher_id')
        sec_id = request.form.get('sec_id')

        if not (course_id and teacher_id and sec_id):
            # simple validation
            return render_template('course_teacher_mapping.html', mappings=CourseTeacherMapping.query.all(),
                                   courses=Course.query.all(), teachers=Teacher.query.all(),
                                   sections=StudentSection.query.all(), error="Please fill all fields")

        mapping = CourseTeacherMapping(
            course_id=course_id,
            teacher_id=teacher_id,
            sec_id=sec_id
        )
        db.session.add(mapping)
        db.session.commit()
        return redirect(url_for('manage_course_teacher_mapping'))
    
    mappings = CourseTeacherMapping.query.all()
    courses = Course.query.all()
    teachers = Teacher.query.all()
    sections = StudentSection.query.all()
    return render_template('course_teacher_mapping.html', mappings=mappings, courses=courses, teachers=teachers, sections=sections)



# --- Timetable Generation ---
@app.route('/generate_timetable', methods=['POST'])
def generate_timetable():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        print("Starting timetable generation...")
        courses = Course.query.all()
        teachers = Teacher.query.all()
        classrooms = Classroom.query.all()

        # Use StudentSection (or StudentGroup) depending on your model
        # If your GA expects 'sections' then use StudentSection
        sections = StudentSection.query.all()

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        time_slots = ["09:00-10:30", "10:30-12:00", "13:00-14:30", "14:30-16:00"]

        # Call GA using positional args (order must match the GA signature)
        best_timetable_df = run_genetic_algorithm(
            courses,        # 1st arg
            teachers,       # 2nd arg
            classrooms,     # 3rd arg (rooms)
            StudentSection.query.all(),       # 4th arg (sections)
            days,           # 5th arg
            time_slots,     # 6th arg
            population_size=100,
            generations=50,
            mutation_rate=0.05
        )

        if best_timetable_df is None or best_timetable_df.empty:
            return jsonify({"error": "Could not generate a valid timetable. Check constraints."}), 500

        print("Saving generated timetable to the database...")
        db.session.query(TimetableEntry).delete()

        # Adjust column names in row indexing below to match what your GA returns:
        # expected columns: day, time_slot, course_id, teacher_id, room_id, section_id
        for index, row in best_timetable_df.iterrows():
            entry = TimetableEntry(
                day=row['day'],
                time_slot=row['time_slot'],
                course_id=row['course_id'],
                teacher_id=row['teacher_id'],
                classroom_id=row['room_id'],
                section_id=row['section_id']   # ✅ use section_id
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
                "course": entry.course.course_name,
                "teacher": entry.teacher.teacher_name,
                "room": entry.classroom.room_id,
                "section": entry.section.section_id   # ✅ use section instead of group
            })

    return render_template('timetable.html', timetable_grid=timetable_grid, days=days, time_slots=time_slots)



@app.route('/analytics')
def analytics():
    if not is_admin(): return redirect(url_for('login'))
    room_utilization = {"Room A": 75, "Room B": 50, "Lab 1": 90}
    faculty_workload = {"Teacher X": 18, "Teacher Y": 15}
    return render_template('analytics.html', room_utilization=room_utilization, faculty_workload=faculty_workload)


def create_db():
    with app.app_context():
        db.create_all()

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

        # Ensure timetable_entry.section_id exists (simple SQLite migration)
        try:
            result = db.session.execute(text("PRAGMA table_info(timetable_entry)"))
            columns = {row[1] for row in result}
            if 'section_id' not in columns:
                print("Adding missing column 'section_id' to 'timetable_entry'...")
                db.session.execute(text("ALTER TABLE timetable_entry ADD COLUMN section_id VARCHAR(20)"))
                db.session.commit()
                print("Column 'section_id' added.")
        except Exception as e:
            db.session.rollback()
            print(f"Schema check/upgrade failed: {e}")

# Flask 3 compatible: run DB init once on the first request
db_initialized = False

@app.before_request
def ensure_db_on_flask_run():
    global db_initialized
    if not db_initialized:
        create_db()
        db_initialized = True


if __name__ == '__main__':
    create_db()
    app.run(debug=True)

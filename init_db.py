# init_db.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import json

app = Flask(__name__)
# Use env vars in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scheduler_dev.db'  # change to MySQL URI in prod
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# -------------------------
# Core Models
# -------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)  # store hashed
    role = db.Column(db.String(20), nullable=False)  # admin / teacher / student

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(100))
    # workload
    max_hours_per_day = db.Column(db.Integer, nullable=True)
    max_hours_per_week = db.Column(db.Integer, nullable=True)
    min_gap_between_classes = db.Column(db.Integer, nullable=True, default=0)
    # contact
    email = db.Column(db.String(200), nullable=True)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(150), nullable=False)
    year = db.Column(db.Integer, nullable=False)  # 1..4 etc.
    branch = db.Column(db.String(100), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('student_group.id'), nullable=True)

class StudentGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)  # e.g., CSE-2A
    size = db.Column(db.Integer, nullable=True)
    students = db.relationship('Student', backref='group', lazy=True)

# Courses + electives
class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(200), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    # core / elective / priority
    is_elective = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, default=0)  # higher => more important
    # room requirements
    required_room_type = db.Column(db.String(50), nullable=True)  # 'lab'|'lecture'
    required_capacity = db.Column(db.Integer, nullable=True)
    required_features = db.Column(db.String(600), nullable=True)  # JSON list
    duration = db.Column(db.Integer, default=1)  # contiguous slots needed

    def get_required_features(self):
        try:
            return json.loads(self.required_features or "[]")
        except:
            return []

# normalized room features (optional)
class RoomFeature(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    capacity = db.Column(db.Integer, nullable=False, default=30)
    room_type = db.Column(db.String(50), nullable=False, default='lecture')
    features = db.Column(db.String(600), nullable=True)  # JSON list of features

    def get_features(self):
        try:
            return json.loads(self.features or "[]")
        except:
            return []

# mapping which group attends which course (handles electives & cross-year)
class CourseAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('student_group.id'), nullable=False)
    # additional attrs: is_primary, seat_limit
    seat_limit = db.Column(db.Integer, nullable=True)

# Substitutions (teacher replacements)
class Substitution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    substitute_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(300), nullable=True)
    approved = db.Column(db.Boolean, default=False)

# Holidays & special days
class Holiday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    name = db.Column(db.String(200))

# Attendance (basic)
class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # present / absent / excused

# Exam scheduling model
class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('student_group.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_slot = db.Column(db.Integer, nullable=False)
    duration = db.Column(db.Integer, default=1)

# Timetable runs & entries (versioning)
class TimetableRun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    notes = db.Column(db.String(300), nullable=True)

class TimetableEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('timetable_run.id'), nullable=True)
    day = db.Column(db.String(10), nullable=False)
    start_slot = db.Column(db.Integer, nullable=False)
    duration = db.Column(db.Integer, default=1)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('student_group.id'), nullable=False)
    # denormalized snapshot for history
    course_name = db.Column(db.String(300))
    teacher_name = db.Column(db.String(300))
    room_name = db.Column(db.String(300))
    group_name = db.Column(db.String(300))

# Manual locks for drag-drop / manual edits
class ManualLock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('timetable_entry.id'), unique=True)
    locked_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    locked_at = db.Column(db.DateTime, default=datetime.utcnow)

# Config table for soft-constraint weights
class ConstraintWeight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True)
    weight = db.Column(db.Float, default=1.0)

# Quick helper to create DB
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Created DB (sqlite dev) - switch to production DB URI before deploy.")

import json
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator
from extensions import db

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

# Use JsonEncodedDict for SQLite, and the native JSON for others.
# We read the DB_URL from the environment to avoid needing an app context at import time.
db_url = os.getenv('DATABASE_URL', 'sqlite:///timetable.db')
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
    email = db.Column(db.String(120), unique=True, nullable=True)
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
    grade = relationship("Grade", backref="sections")
    department = relationship("Department", backref="sections")

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
    duration = db.Column(db.Integer, nullable=False, default=180)  # Duration in minutes
    type = db.Column(db.String(20), nullable=False, default='final')  # final, midterm, quiz
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    
    # Relationships
    subject = relationship("Subject", backref="exams")
    course = relationship("Course", backref="exams")
    seating_plans = relationship("ExamSeating", backref="exam", cascade="all, delete-orphan")

class ExamSeating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False)
    seat_number = db.Column(db.String(10))
    
    # Relationships
    student = relationship("Student", backref="exam_seatings")
    classroom = relationship("Classroom", backref="exam_seatings")

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


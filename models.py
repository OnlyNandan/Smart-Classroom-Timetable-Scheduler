"""
Database models for Edu-Sync AI
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for all roles (Admin, Teacher, Student, Parent)"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, teacher, student, parent
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    teacher_profile = db.relationship('Teacher', backref='user', uselist=False, cascade='all, delete-orphan')
    student_profile = db.relationship('Student', backref='user', uselist=False, cascade='all, delete-orphan')
    parent_profile = db.relationship('Parent', backref='user', uselist=False, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

class Teacher(db.Model):
    """Teacher profile with qualifications and workload limits"""
    __tablename__ = 'teachers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    employee_id = db.Column(db.String(20), unique=True, nullable=False)
    qualifications = db.Column(db.Text)
    max_hours_week = db.Column(db.Integer, default=40)
    specialization = db.Column(db.String(100))
    joining_date = db.Column(db.Date)
    is_available = db.Column(db.Boolean, default=True)
    
    # Relationships
    subjects = db.relationship('Subject', backref='teacher')
    timetable_entries = db.relationship('TimetableEntry', backref='teacher')
    attendance_records = db.relationship('Attendance', backref='teacher')

class Student(db.Model):
    """Student profile with academic information"""
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    student_id = db.Column(db.String(20), unique=True, nullable=False)
    admission_number = db.Column(db.String(20), unique=True)
    grade = db.Column(db.String(10), nullable=False)  # UKG, 1, 2, ..., 12, College
    section = db.Column(db.String(10), nullable=False)  # A, B, C, etc.
    date_of_birth = db.Column(db.Date)
    admission_date = db.Column(db.Date, default=datetime.utcnow)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'))
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    timetable_entries = db.relationship('TimetableEntry', backref='section_student')
    exam_assignments = db.relationship('ExamAssignment', backref='student')
    elective_selections = db.relationship('ElectiveSelection', backref='student')

class Parent(db.Model):
    """Parent profile"""
    __tablename__ = 'parents'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    occupation = db.Column(db.String(100))
    address = db.Column(db.Text)
    emergency_contact = db.Column(db.String(20))
    
    # Relationships
    children = db.relationship('Student', backref='parent')

class Subject(db.Model):
    """Subject/Course information"""
    __tablename__ = 'subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    weekly_hours = db.Column(db.Integer, nullable=False)
    grade_level = db.Column(db.String(20), nullable=False)  # UKG-12, College
    requires_lab = db.Column(db.Boolean, default=False)
    is_elective = db.Column(db.Boolean, default=False)
    max_students = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    timetable_entries = db.relationship('TimetableEntry', backref='subject')
    exam_schedules = db.relationship('ExamSchedule', backref='subject')

class Room(db.Model):
    """Classroom/Lab information"""
    __tablename__ = 'rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    room_type = db.Column(db.String(20), nullable=False)  # Classroom, Lab, Library, Sports
    floor = db.Column(db.Integer)
    building = db.Column(db.String(50))
    equipment = db.Column(db.Text)  # JSON string of available equipment
    is_available = db.Column(db.Boolean, default=True)
    
    # Relationships
    timetable_entries = db.relationship('TimetableEntry', backref='room')
    exam_assignments = db.relationship('ExamAssignment', backref='room')

class TimetableEntry(db.Model):
    """Individual timetable entries"""
    __tablename__ = 'timetable_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    day_of_week = db.Column(db.String(10), nullable=False)  # Monday, Tuesday, etc.
    time_slot = db.Column(db.String(20), nullable=False)  # 09:00-10:00
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    grade = db.Column(db.String(10), nullable=False)
    section = db.Column(db.String(10), nullable=False)
    timetable_version = db.Column(db.String(50), nullable=False)  # To track different versions
    is_manual_override = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Index for performance
    __table_args__ = (
        db.Index('idx_timetable_lookup', 'day_of_week', 'time_slot', 'grade', 'section'),
        db.Index('idx_teacher_schedule', 'teacher_id', 'day_of_week', 'time_slot'),
        db.Index('idx_room_schedule', 'room_id', 'day_of_week', 'time_slot'),
    )

class ExamSchedule(db.Model):
    """Exam scheduling information"""
    __tablename__ = 'exam_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    exam_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    grade = db.Column(db.String(10), nullable=False)
    exam_type = db.Column(db.String(20), default='Final')  # Mid-term, Final, Quiz
    total_students = db.Column(db.Integer)
    is_seating_plan_generated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ExamAssignment(db.Model):
    """Student exam room and seat assignments"""
    __tablename__ = 'exam_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_schedule_id = db.Column(db.Integer, db.ForeignKey('exam_schedules.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    seat_number = db.Column(db.String(10))  # A1, B2, etc.
    row = db.Column(db.Integer)
    column = db.Column(db.Integer)
    
    # Relationships
    exam_schedule = db.relationship('ExamSchedule', backref='assignments')

class ElectiveSelection(db.Model):
    """Student elective subject selections"""
    __tablename__ = 'elective_selections'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    academic_year = db.Column(db.String(10), nullable=False)
    semester = db.Column(db.String(20))
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    subject = db.relationship('Subject', backref='elective_selections')

class Attendance(db.Model):
    """Attendance records"""
    __tablename__ = 'attendance'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False)  # Present, Absent, Late
    remarks = db.Column(db.Text)
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    """System notifications"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    recipient_type = db.Column(db.String(20), nullable=False)  # all, admin, teacher, student, parent
    recipient_id = db.Column(db.Integer)  # Specific user ID if targeted
    notification_type = db.Column(db.String(20), default='info')  # info, warning, error, success
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)

class TimetableVersion(db.Model):
    """Track different timetable versions"""
    __tablename__ = 'timetable_versions'
    
    id = db.Column(db.Integer, primary_key=True)
    version_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    academic_year = db.Column(db.String(10), nullable=False)
    semester = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=False)
    generated_by = db.Column(db.String(20), default='AI')  # AI, Manual, Import
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))

class AuditLog(db.Model):
    """Audit trail for all major actions"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50))
    resource_id = db.Column(db.String(50))
    details = db.Column(db.Text)  # JSON string of action details
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='audit_logs')
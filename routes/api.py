"""
RESTful API routes for Edu-Sync AI
Mobile app support and external integrations
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, User, Teacher, Student, Parent, Subject, Room, TimetableEntry, ExamSchedule, ExamAssignment, Attendance
from datetime import datetime, date
import json

api_bp = Blueprint('api', __name__)

# API Authentication decorator
def api_auth_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# API Response helpers
def success_response(data=None, message="Success"):
    response = {'success': True, 'message': message}
    if data is not None:
        response['data'] = data
    return jsonify(response)

def error_response(message="Error", status_code=400):
    return jsonify({'success': False, 'error': message}), status_code

# User Profile API
@api_bp.route('/profile', methods=['GET', 'PUT'])
@api_auth_required
def profile():
    if request.method == 'GET':
        profile_data = {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'first_name': current_user.first_name,
            'last_name': current_user.last_name,
            'role': current_user.role,
            'phone': current_user.phone
        }
        
        # Add role-specific profile data
        if current_user.role == 'teacher' and current_user.teacher_profile:
            teacher = current_user.teacher_profile
            profile_data.update({
                'employee_id': teacher.employee_id,
                'specialization': teacher.specialization,
                'qualifications': teacher.qualifications,
                'max_hours_week': teacher.max_hours_week
            })
        elif current_user.role == 'student' and current_user.student_profile:
            student = current_user.student_profile
            profile_data.update({
                'student_id': student.student_id,
                'grade': student.grade,
                'section': student.section,
                'admission_number': student.admission_number
            })
        elif current_user.role == 'parent' and current_user.parent_profile:
            parent = current_user.parent_profile
            profile_data.update({
                'occupation': parent.occupation,
                'address': parent.address
            })
        
        return success_response(profile_data)
    
    elif request.method == 'PUT':
        data = request.get_json()
        
        try:
            current_user.first_name = data.get('first_name', current_user.first_name)
            current_user.last_name = data.get('last_name', current_user.last_name)
            current_user.phone = data.get('phone', current_user.phone)
            
            # Update role-specific profile
            if current_user.role == 'teacher' and current_user.teacher_profile:
                teacher = current_user.teacher_profile
                teacher.specialization = data.get('specialization', teacher.specialization)
                teacher.qualifications = data.get('qualifications', teacher.qualifications)
            elif current_user.role == 'parent' and current_user.parent_profile:
                parent = current_user.parent_profile
                parent.occupation = data.get('occupation', parent.occupation)
                parent.address = data.get('address', parent.address)
            
            db.session.commit()
            return success_response(message="Profile updated successfully")
            
        except Exception as e:
            db.session.rollback()
            return error_response(f"Update failed: {str(e)}", 500)

# Timetable API
@api_bp.route('/timetable', methods=['GET'])
@api_auth_required
def get_timetable():
    try:
        if current_user.role == 'teacher':
            teacher = Teacher.query.filter_by(user_id=current_user.id).first()
            if not teacher:
                return error_response("Teacher profile not found", 404)
            
            entries = TimetableEntry.query.filter_by(teacher_id=teacher.id).all()
            
        elif current_user.role == 'student':
            student = Student.query.filter_by(user_id=current_user.id).first()
            if not student:
                return error_response("Student profile not found", 404)
            
            entries = TimetableEntry.query.filter_by(
                grade=student.grade, 
                section=student.section
            ).all()
            
        elif current_user.role == 'parent':
            parent = Parent.query.filter_by(user_id=current_user.id).first()
            if not parent:
                return error_response("Parent profile not found", 404)
            
            # Get children's timetables
            children = Student.query.filter_by(parent_id=parent.id).all()
            entries = []
            for child in children:
                child_entries = TimetableEntry.query.filter_by(
                    grade=child.grade, 
                    section=child.section
                ).all()
                entries.extend(child_entries)
        
        else:
            return error_response("Invalid role", 403)
        
        # Format timetable data
        timetable_data = []
        for entry in entries:
            timetable_data.append({
                'id': entry.id,
                'day': entry.day_of_week,
                'time_slot': entry.time_slot,
                'subject': {
                    'id': entry.subject.id,
                    'name': entry.subject.name,
                    'code': entry.subject.code
                },
                'teacher': {
                    'id': entry.teacher.id,
                    'name': entry.teacher.user.get_full_name()
                },
                'room': {
                    'id': entry.room.id,
                    'number': entry.room.room_number,
                    'name': entry.room.name
                },
                'grade': entry.grade,
                'section': entry.section
            })
        
        return success_response(timetable_data)
        
    except Exception as e:
        return error_response(f"Failed to fetch timetable: {str(e)}", 500)

# Exam Schedule API
@api_bp.route('/exams', methods=['GET'])
@api_auth_required
def get_exams():
    try:
        if current_user.role == 'student':
            student = Student.query.filter_by(user_id=current_user.id).first()
            if not student:
                return error_response("Student profile not found", 404)
            
            exams = ExamSchedule.query.filter_by(grade=student.grade).all()
            assignments = ExamAssignment.query.filter_by(student_id=student.id).all()
            
        elif current_user.role == 'parent':
            parent = Parent.query.filter_by(user_id=current_user.id).first()
            if not parent:
                return error_response("Parent profile not found", 404)
            
            children = Student.query.filter_by(parent_id=parent.id).all()
            exams = []
            assignments = []
            
            for child in children:
                child_exams = ExamSchedule.query.filter_by(grade=child.grade).all()
                exams.extend(child_exams)
                
                child_assignments = ExamAssignment.query.filter_by(student_id=child.id).all()
                assignments.extend(child_assignments)
        
        else:
            return error_response("Invalid role", 403)
        
        # Format exam data
        exam_data = []
        assignment_map = {a.exam_schedule_id: a for a in assignments}
        
        for exam in exams:
            assignment = assignment_map.get(exam.id)
            exam_info = {
                'id': exam.id,
                'subject': {
                    'id': exam.subject.id,
                    'name': exam.subject.name,
                    'code': exam.subject.code
                },
                'date': exam.exam_date.isoformat(),
                'start_time': exam.start_time.strftime('%H:%M'),
                'end_time': exam.end_time.strftime('%H:%M'),
                'duration_minutes': exam.duration_minutes,
                'exam_type': exam.exam_type,
                'grade': exam.grade
            }
            
            if assignment:
                exam_info['assignment'] = {
                    'room_id': assignment.room_id,
                    'room_number': assignment.room.room_number,
                    'seat_number': assignment.seat_number,
                    'row': assignment.row,
                    'column': assignment.column
                }
            
            exam_data.append(exam_info)
        
        return success_response(exam_data)
        
    except Exception as e:
        return error_response(f"Failed to fetch exams: {str(e)}", 500)

# Attendance API
@api_bp.route('/attendance', methods=['GET'])
@api_auth_required
def get_attendance():
    try:
        if current_user.role == 'student':
            student = Student.query.filter_by(user_id=current_user.id).first()
            if not student:
                return error_response("Student profile not found", 404)
            
            records = Attendance.query.filter_by(student_id=student.id).all()
            
        elif current_user.role == 'parent':
            parent = Parent.query.filter_by(user_id=current_user.id).first()
            if not parent:
                return error_response("Parent profile not found", 404)
            
            children = Student.query.filter_by(parent_id=parent.id).all()
            records = []
            
            for child in children:
                child_records = Attendance.query.filter_by(student_id=child.id).all()
                records.extend(child_records)
        
        else:
            return error_response("Invalid role", 403)
        
        # Format attendance data
        attendance_data = []
        for record in records:
            attendance_data.append({
                'id': record.id,
                'date': record.date.isoformat(),
                'status': record.status,
                'remarks': record.remarks,
                'subject': {
                    'id': record.subject.id,
                    'name': record.subject.name,
                    'code': record.subject.code
                },
                'teacher': {
                    'id': record.teacher.id,
                    'name': record.teacher.user.get_full_name()
                }
            })
        
        return success_response(attendance_data)
        
    except Exception as e:
        return error_response(f"Failed to fetch attendance: {str(e)}", 500)

# Google Calendar Integration API
@api_bp.route('/calendar/export', methods=['GET'])
@api_auth_required
def export_calendar():
    try:
        from utils.export_helpers import ExportHelper
        
        export_helper = ExportHelper()
        calendar_data = export_helper.generate_ical_export(current_user)
        
        return success_response(calendar_data)
        
    except Exception as e:
        return error_response(f"Failed to export calendar: {str(e)}", 500)

# Notifications API
@api_bp.route('/notifications', methods=['GET'])
@api_auth_required
def get_notifications():
    try:
        from models import Notification
        
        notifications = Notification.query.filter(
            (Notification.recipient_type == current_user.role) |
            (Notification.recipient_type == 'all') |
            (Notification.recipient_id == current_user.id)
        ).order_by(Notification.created_at.desc()).limit(50).all()
        
        notification_data = []
        for notification in notifications:
            notification_data.append({
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'type': notification.notification_type,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat(),
                'expires_at': notification.expires_at.isoformat() if notification.expires_at else None
            })
        
        return success_response(notification_data)
        
    except Exception as e:
        return error_response(f"Failed to fetch notifications: {str(e)}", 500)

@api_bp.route('/notifications/<int:notification_id>/read', methods=['PUT'])
@api_auth_required
def mark_notification_read(notification_id):
    try:
        from models import Notification
        
        notification = Notification.query.get_or_404(notification_id)
        notification.is_read = True
        db.session.commit()
        
        return success_response(message="Notification marked as read")
        
    except Exception as e:
        return error_response(f"Failed to mark notification as read: {str(e)}", 500)

# Elective Selection API
@api_bp.route('/electives', methods=['GET', 'POST'])
@api_auth_required
def electives():
    if current_user.role != 'student':
        return error_response("Access denied", 403)
    
    try:
        student = Student.query.filter_by(user_id=current_user.id).first()
        if not student:
            return error_response("Student profile not found", 404)
        
        if request.method == 'GET':
            # Get available electives
            elective_subjects = Subject.query.filter_by(
                grade_level=student.grade,
                is_elective=True
            ).all()
            
            # Get current selections
            from models import ElectiveSelection
            current_selections = ElectiveSelection.query.filter_by(student_id=student.id).all()
            selected_ids = [s.subject_id for s in current_selections]
            
            electives_data = []
            for subject in elective_subjects:
                electives_data.append({
                    'id': subject.id,
                    'code': subject.code,
                    'name': subject.name,
                    'description': subject.description,
                    'weekly_hours': subject.weekly_hours,
                    'is_selected': subject.id in selected_ids
                })
            
            return success_response(electives_data)
        
        elif request.method == 'POST':
            data = request.get_json()
            selected_subjects = data.get('selected_subjects', [])
            academic_year = data.get('academic_year', '2024-25')
            
            # Clear existing selections
            from models import ElectiveSelection
            ElectiveSelection.query.filter_by(
                student_id=student.id,
                academic_year=academic_year
            ).delete()
            
            # Add new selections
            for subject_id in selected_subjects:
                elective_selection = ElectiveSelection(
                    student_id=student.id,
                    subject_id=subject_id,
                    academic_year=academic_year
                )
                db.session.add(elective_selection)
            
            db.session.commit()
            return success_response(message="Elective selections updated successfully")
            
    except Exception as e:
        return error_response(f"Failed to handle electives: {str(e)}", 500)

# Health Check API
@api_bp.route('/health', methods=['GET'])
def health_check():
    try:
        # Basic health checks
        db.session.execute('SELECT 1')
        
        return success_response({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected'
        })
        
    except Exception as e:
        return error_response(f"Health check failed: {str(e)}", 500)

# API Documentation endpoint
@api_bp.route('/docs', methods=['GET'])
def api_docs():
    docs = {
        'version': '1.0',
        'base_url': '/api',
        'endpoints': {
            'GET /profile': 'Get user profile',
            'PUT /profile': 'Update user profile',
            'GET /timetable': 'Get user timetable',
            'GET /exams': 'Get exam schedule',
            'GET /attendance': 'Get attendance records',
            'GET /calendar/export': 'Export calendar data',
            'GET /notifications': 'Get notifications',
            'PUT /notifications/<id>/read': 'Mark notification as read',
            'GET /electives': 'Get available electives (students only)',
            'POST /electives': 'Update elective selections (students only)',
            'GET /health': 'Health check'
        },
        'authentication': 'Login required for all endpoints except /health and /docs',
        'response_format': {
            'success': True,
            'message': 'Success message',
            'data': 'Response data (optional)'
        }
    }
    
    return jsonify(docs)
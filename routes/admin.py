"""
Admin routes for Edu-Sync AI
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from models import db, User, Teacher, Student, Parent, Subject, Room, TimetableEntry, ExamSchedule, Notification
from utils.ai_helpers import AIHelper
from utils.export_helpers import ExportHelper
import pandas as pd
import json
from datetime import datetime, timedelta
import os

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    # Dashboard statistics
    stats = {
        'total_teachers': Teacher.query.count(),
        'total_students': Student.query.count(),
        'total_subjects': Subject.query.count(),
        'total_rooms': Room.query.count(),
        'active_timetables': TimetableEntry.query.distinct(TimetableEntry.timetable_version).count(),
        'upcoming_exams': ExamSchedule.query.filter(ExamSchedule.exam_date >= datetime.now().date()).count()
    }
    
    # Recent notifications
    recent_notifications = Notification.query.order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', stats=stats, notifications=recent_notifications)

@admin_bp.route('/users')
@login_required
def users():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/teachers')
@login_required
def teachers():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    teachers = Teacher.query.join(User).all()
    return render_template('admin/teachers.html', teachers=teachers)

@admin_bp.route('/students')
@login_required
def students():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    grade = request.args.get('grade')
    section = request.args.get('section')
    
    query = Student.query.join(User)
    if grade:
        query = query.filter(Student.grade == grade)
    if section:
        query = query.filter(Student.section == section)
    
    students = query.all()
    grades = db.session.query(Student.grade).distinct().all()
    sections = db.session.query(Student.section).distinct().all()
    
    return render_template('admin/students.html', students=students, grades=grades, sections=sections)

@admin_bp.route('/subjects')
@login_required
def subjects():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    subjects = Subject.query.join(Teacher, Teacher.id == Subject.teacher_id, isouter=True).join(User, User.id == Teacher.user_id, isouter=True).all()
    return render_template('admin/subjects.html', subjects=subjects)

@admin_bp.route('/rooms')
@login_required
def rooms():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    rooms = Room.query.all()
    return render_template('admin/rooms.html', rooms=rooms)

@admin_bp.route('/bulk-import', methods=['GET', 'POST'])
@login_required
def bulk_import():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        file_type = request.form.get('file_type')
        file = request.files.get('file')
        
        if file and file.filename:
            try:
                df = pd.read_csv(file)
                
                if file_type == 'students':
                    imported_count = import_students(df)
                    flash(f'Successfully imported {imported_count} students.', 'success')
                elif file_type == 'teachers':
                    imported_count = import_teachers(df)
                    flash(f'Successfully imported {imported_count} teachers.', 'success')
                elif file_type == 'subjects':
                    imported_count = import_subjects(df)
                    flash(f'Successfully imported {imported_count} subjects.', 'success')
                else:
                    flash('Invalid file type.', 'error')
                
            except Exception as e:
                flash(f'Import failed: {str(e)}', 'error')
        else:
            flash('No file selected.', 'error')
    
    return render_template('admin/bulk_import.html')

def import_students(df):
    """Import students from CSV"""
    count = 0
    for _, row in df.iterrows():
        try:
            # Create user
            user = User(
                username=row['username'],
                email=row['email'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                role='student',
                phone=row.get('phone', '')
            )
            user.set_password(row.get('password', 'password123'))
            
            db.session.add(user)
            db.session.flush()  # Get user ID
            
            # Create student profile
            student = Student(
                user_id=user.id,
                student_id=row['student_id'],
                admission_number=row.get('admission_number'),
                grade=row['grade'],
                section=row['section'],
                date_of_birth=pd.to_datetime(row.get('date_of_birth')).date() if pd.notna(row.get('date_of_birth')) else None
            )
            
            db.session.add(student)
            count += 1
            
        except Exception as e:
            print(f"Error importing student {row.get('username', 'unknown')}: {str(e)}")
            continue
    
    db.session.commit()
    return count

def import_teachers(df):
    """Import teachers from CSV"""
    count = 0
    for _, row in df.iterrows():
        try:
            # Create user
            user = User(
                username=row['username'],
                email=row['email'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                role='teacher',
                phone=row.get('phone', '')
            )
            user.set_password(row.get('password', 'password123'))
            
            db.session.add(user)
            db.session.flush()  # Get user ID
            
            # Create teacher profile
            teacher = Teacher(
                user_id=user.id,
                employee_id=row['employee_id'],
                qualifications=row.get('qualifications', ''),
                specialization=row.get('specialization', ''),
                max_hours_week=int(row.get('max_hours_week', 40))
            )
            
            db.session.add(teacher)
            count += 1
            
        except Exception as e:
            print(f"Error importing teacher {row.get('username', 'unknown')}: {str(e)}")
            continue
    
    db.session.commit()
    return count

def import_subjects(df):
    """Import subjects from CSV"""
    count = 0
    for _, row in df.iterrows():
        try:
            teacher = Teacher.query.filter_by(employee_id=row.get('teacher_id')).first()
            
            subject = Subject(
                code=row['code'],
                name=row['name'],
                description=row.get('description', ''),
                teacher_id=teacher.id if teacher else None,
                weekly_hours=int(row['weekly_hours']),
                grade_level=row['grade_level'],
                requires_lab=bool(row.get('requires_lab', False)),
                is_elective=bool(row.get('is_elective', False)),
                max_students=int(row.get('max_students', 0)) if pd.notna(row.get('max_students')) else None
            )
            
            db.session.add(subject)
            count += 1
            
        except Exception as e:
            print(f"Error importing subject {row.get('code', 'unknown')}: {str(e)}")
            continue
    
    db.session.commit()
    return count

@admin_bp.route('/timetable/generate', methods=['POST'])
@login_required
def generate_timetable():
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        ai_helper = AIHelper()
        result = ai_helper.generate_timetable()
        
        if result['success']:
            flash('Timetable generated successfully!', 'success')
            return jsonify({'success': True, 'message': 'Timetable generated successfully'})
        else:
            flash(f'Timetable generation failed: {result["error"]}', 'error')
            return jsonify({'success': False, 'error': result['error']})
    
    except Exception as e:
        flash(f'Error generating timetable: {str(e)}', 'error')
        return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/timetable/view')
@login_required
def view_timetable():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    version = request.args.get('version', 'latest')
    grade = request.args.get('grade')
    section = request.args.get('section')
    
    query = TimetableEntry.query
    if version != 'latest':
        query = query.filter(TimetableEntry.timetable_version == version)
    if grade:
        query = query.filter(TimetableEntry.grade == grade)
    if section:
        query = query.filter(TimetableEntry.section == section)
    
    timetable_entries = query.order_by(TimetableEntry.day_of_week, TimetableEntry.time_slot).all()
    
    # Get available versions
    versions = db.session.query(TimetableEntry.timetable_version).distinct().all()
    grades = db.session.query(TimetableEntry.grade).distinct().all()
    sections = db.session.query(TimetableEntry.section).distinct().all()
    
    return render_template('admin/timetable_view.html', 
                         timetable_entries=timetable_entries,
                         versions=versions, grades=grades, sections=sections)

@admin_bp.route('/timetable/repair', methods=['POST'])
@login_required
def repair_timetable():
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        ai_helper = AIHelper()
        result = ai_helper.repair_timetable()
        
        if result['success']:
            flash('Timetable repaired successfully!', 'success')
            return jsonify({'success': True, 'message': 'Timetable repaired successfully'})
        else:
            flash(f'Timetable repair failed: {result["error"]}', 'error')
            return jsonify({'success': False, 'error': result['error']})
    
    except Exception as e:
        flash(f'Error repairing timetable: {str(e)}', 'error')
        return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/exam/schedule', methods=['GET', 'POST'])
@login_required
def exam_schedule():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            ai_helper = AIHelper()
            result = ai_helper.generate_exam_schedule()
            
            if result['success']:
                flash('Exam schedule generated successfully!', 'success')
                return redirect(url_for('admin.exam_schedule'))
            else:
                flash(f'Exam scheduling failed: {result["error"]}', 'error')
        
        except Exception as e:
            flash(f'Error scheduling exams: {str(e)}', 'error')
    
    exams = ExamSchedule.query.order_by(ExamSchedule.exam_date).all()
    return render_template('admin/exam_schedule.html', exams=exams)

@admin_bp.route('/notifications', methods=['GET', 'POST'])
@login_required
def notifications():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        message = request.form.get('message')
        recipient_type = request.form.get('recipient_type')
        notification_type = request.form.get('notification_type')
        
        notification = Notification(
            title=title,
            message=message,
            recipient_type=recipient_type,
            notification_type=notification_type
        )
        
        db.session.add(notification)
        db.session.commit()
        
        flash('Notification sent successfully!', 'success')
        return redirect(url_for('admin.notifications'))
    
    notifications = Notification.query.order_by(Notification.created_at.desc()).all()
    return render_template('admin/notifications.html', notifications=notifications)

@admin_bp.route('/export/timetable')
@login_required
def export_timetable():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    format_type = request.args.get('format', 'pdf')
    version = request.args.get('version', 'latest')
    grade = request.args.get('grade')
    section = request.args.get('section')
    
    try:
        export_helper = ExportHelper()
        file_path = export_helper.export_timetable(format_type, version, grade, section)
        
        return send_file(file_path, as_attachment=True)
    
    except Exception as e:
        flash(f'Export failed: {str(e)}', 'error')
        return redirect(url_for('admin.view_timetable'))

@admin_bp.route('/export/exam-schedule')
@login_required
def export_exam_schedule():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    format_type = request.args.get('format', 'pdf')
    grade = request.args.get('grade')
    
    try:
        export_helper = ExportHelper()
        file_path = export_helper.export_exam_schedule(format_type, grade)
        
        return send_file(file_path, as_attachment=True)
    
    except Exception as e:
        flash(f'Export failed: {str(e)}', 'error')
        return redirect(url_for('admin.exam_schedule'))
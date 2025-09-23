"""
Teacher routes for Edu-Sync AI
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Teacher, TimetableEntry, Attendance, Student, Subject
from datetime import datetime, date, timedelta

teacher_bp = Blueprint('teacher', __name__)

@teacher_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'teacher':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        flash('Teacher profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get teacher's timetable for current week
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    timetable = TimetableEntry.query.filter_by(teacher_id=teacher.id).order_by(
        TimetableEntry.day_of_week, TimetableEntry.time_slot
    ).all()
    
    # Get today's classes
    today_classes = [entry for entry in timetable if entry.day_of_week == today.strftime('%A')]
    
    # Get attendance stats for the month
    month_start = today.replace(day=1)
    attendance_stats = db.session.query(
        Attendance.status,
        db.func.count(Attendance.id)
    ).filter(
        Attendance.teacher_id == teacher.id,
        Attendance.date >= month_start
    ).group_by(Attendance.status).all()
    
    return render_template('teacher/dashboard.html', 
                         teacher=teacher, 
                         timetable=timetable,
                         today_classes=today_classes,
                         attendance_stats=attendance_stats)

@teacher_bp.route('/timetable')
@login_required
def timetable():
    if current_user.role != 'teacher':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        flash('Teacher profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get teacher's full timetable
    timetable_entries = TimetableEntry.query.filter_by(teacher_id=teacher.id).order_by(
        TimetableEntry.day_of_week, TimetableEntry.time_slot
    ).all()
    
    # Group by day for easier display
    timetable_by_day = {}
    for entry in timetable_entries:
        day = entry.day_of_week
        if day not in timetable_by_day:
            timetable_by_day[day] = []
        timetable_by_day[day].append(entry)
    
    return render_template('teacher/timetable.html', 
                         timetable_by_day=timetable_by_day,
                         teacher=teacher)

@teacher_bp.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    if current_user.role != 'teacher':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        flash('Teacher profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        date_str = request.form.get('date')
        grade = request.form.get('grade')
        section = request.form.get('section')
        
        # Get students for the class
        students = Student.query.filter_by(grade=grade, section=section).all()
        
        # Mark attendance for each student
        for student in students:
            status = request.form.get(f'status_{student.id}', 'Absent')
            remarks = request.form.get(f'remarks_{student.id}', '')
            
            attendance = Attendance(
                student_id=student.id,
                teacher_id=teacher.id,
                subject_id=subject_id,
                date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                status=status,
                remarks=remarks
            )
            
            db.session.add(attendance)
        
        db.session.commit()
        flash('Attendance marked successfully!', 'success')
        return redirect(url_for('teacher.attendance'))
    
    # Get teacher's subjects and classes
    subjects = Subject.query.filter_by(teacher_id=teacher.id).all()
    
    # Get unique grade-section combinations for this teacher
    classes = db.session.query(TimetableEntry.grade, TimetableEntry.section).filter_by(
        teacher_id=teacher.id
    ).distinct().all()
    
    return render_template('teacher/attendance.html', 
                         subjects=subjects, 
                         classes=classes,
                         teacher=teacher)

@teacher_bp.route('/attendance/view')
@login_required
def view_attendance():
    if current_user.role != 'teacher':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        flash('Teacher profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get filters
    subject_id = request.args.get('subject_id')
    grade = request.args.get('grade')
    section = request.args.get('section')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Build query
    query = Attendance.query.filter_by(teacher_id=teacher.id)
    
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    if grade:
        query = query.join(Student).filter(Student.grade == grade)
    if section:
        query = query.join(Student).filter(Student.section == section)
    if start_date:
        query = query.filter(Attendance.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Attendance.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    
    attendance_records = query.order_by(Attendance.date.desc()).all()
    
    # Get filter options
    subjects = Subject.query.filter_by(teacher_id=teacher.id).all()
    classes = db.session.query(TimetableEntry.grade, TimetableEntry.section).filter_by(
        teacher_id=teacher.id
    ).distinct().all()
    
    return render_template('teacher/view_attendance.html',
                         attendance_records=attendance_records,
                         subjects=subjects,
                         classes=classes,
                         teacher=teacher)

@teacher_bp.route('/substitution/request', methods=['GET', 'POST'])
@login_required
def request_substitution():
    if current_user.role != 'teacher':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        flash('Teacher profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    if request.method == 'POST':
        date_str = request.form.get('date')
        time_slot = request.form.get('time_slot')
        reason = request.form.get('reason')
        subject_id = request.form.get('subject_id')
        grade = request.form.get('grade')
        section = request.form.get('section')
        
        # Create substitution request (you might want to create a SubstitutionRequest model)
        # For now, we'll create a notification
        from models import Notification
        
        notification = Notification(
            title=f"Substitution Request - {current_user.get_full_name()}",
            message=f"Teacher {current_user.get_full_name()} has requested substitution for {date_str} at {time_slot}. Reason: {reason}",
            recipient_type='admin',
            notification_type='warning'
        )
        
        db.session.add(notification)
        db.session.commit()
        
        flash('Substitution request submitted successfully!', 'success')
        return redirect(url_for('teacher.request_substitution'))
    
    # Get teacher's timetable for substitution requests
    timetable_entries = TimetableEntry.query.filter_by(teacher_id=teacher.id).order_by(
        TimetableEntry.day_of_week, TimetableEntry.time_slot
    ).all()
    
    return render_template('teacher/substitution_request.html',
                         timetable_entries=timetable_entries,
                         teacher=teacher)

@teacher_bp.route('/profile')
@login_required
def profile():
    if current_user.role != 'teacher':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        flash('Teacher profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    return render_template('teacher/profile.html', teacher=teacher)

@teacher_bp.route('/availability', methods=['GET', 'POST'])
@login_required
def availability():
    if current_user.role != 'teacher':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        flash('Teacher profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    if request.method == 'POST':
        # Update availability status
        teacher.is_available = bool(request.form.get('is_available'))
        db.session.commit()
        
        flash('Availability updated successfully!', 'success')
        return redirect(url_for('teacher.availability'))
    
    return render_template('teacher/availability.html', teacher=teacher)

@teacher_bp.route('/workload')
@login_required
def workload():
    if current_user.role != 'teacher':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if not teacher:
        flash('Teacher profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Calculate current workload
    timetable_entries = TimetableEntry.query.filter_by(teacher_id=teacher.id).all()
    
    # Count hours per day
    hours_per_day = {}
    for entry in timetable_entries:
        day = entry.day_of_week
        if day not in hours_per_day:
            hours_per_day[day] = 0
        
        # Parse time slot to get duration
        start_time, end_time = entry.time_slot.split('-')
        start_hour = int(start_time.split(':')[0])
        end_hour = int(end_time.split(':')[0])
        duration = end_hour - start_hour
        hours_per_day[day] += duration
    
    total_hours = sum(hours_per_day.values())
    max_hours = teacher.max_hours_week
    
    return render_template('teacher/workload.html',
                         teacher=teacher,
                         hours_per_day=hours_per_day,
                         total_hours=total_hours,
                         max_hours=max_hours)
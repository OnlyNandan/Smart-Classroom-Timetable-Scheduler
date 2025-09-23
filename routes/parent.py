"""
Parent routes for Edu-Sync AI
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Parent, Student, TimetableEntry, ExamSchedule, ExamAssignment, Attendance
from datetime import datetime, date, timedelta

parent_bp = Blueprint('parent', __name__)

@parent_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'parent':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    parent = Parent.query.filter_by(user_id=current_user.id).first()
    if not parent:
        flash('Parent profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get parent's children
    children = Student.query.filter_by(parent_id=parent.id).all()
    
    # Get overview data for all children
    children_data = []
    for child in children:
        # Get child's timetable
        timetable_entries = TimetableEntry.query.filter_by(
            grade=child.grade, 
            section=child.section
        ).count()
        
        # Get today's classes
        today = datetime.now().date()
        today_classes = TimetableEntry.query.filter_by(
            grade=child.grade, 
            section=child.section
        ).filter(TimetableEntry.day_of_week == today.strftime('%A')).count()
        
        # Get upcoming exams
        upcoming_exams = ExamSchedule.query.filter(
            ExamSchedule.grade == child.grade,
            ExamSchedule.exam_date >= today
        ).count()
        
        # Get attendance percentage for the month
        month_start = today.replace(day=1)
        attendance_records = Attendance.query.filter(
            Attendance.student_id == child.id,
            Attendance.date >= month_start
        ).all()
        
        total_classes = len(attendance_records)
        present_classes = len([r for r in attendance_records if r.status == 'Present'])
        attendance_percentage = (present_classes / total_classes * 100) if total_classes > 0 else 0
        
        children_data.append({
            'child': child,
            'total_classes': timetable_entries,
            'today_classes': today_classes,
            'upcoming_exams': upcoming_exams,
            'attendance_percentage': attendance_percentage
        })
    
    return render_template('parent/dashboard.html',
                         parent=parent,
                         children_data=children_data)

@parent_bp.route('/child/<int:child_id>/timetable')
@login_required
def child_timetable(child_id):
    if current_user.role != 'parent':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    parent = Parent.query.filter_by(user_id=current_user.id).first()
    if not parent:
        flash('Parent profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Verify child belongs to parent
    child = Student.query.filter_by(id=child_id, parent_id=parent.id).first()
    if not child:
        flash('Child not found or access denied.', 'error')
        return redirect(url_for('parent.dashboard'))
    
    # Get child's timetable
    timetable_entries = TimetableEntry.query.filter_by(
        grade=child.grade, 
        section=child.section
    ).order_by(TimetableEntry.day_of_week, TimetableEntry.time_slot).all()
    
    # Group by day for easier display
    timetable_by_day = {}
    for entry in timetable_entries:
        day = entry.day_of_week
        if day not in timetable_by_day:
            timetable_by_day[day] = []
        timetable_by_day[day].append(entry)
    
    return render_template('parent/child_timetable.html',
                         timetable_by_day=timetable_by_day,
                         child=child,
                         parent=parent)

@parent_bp.route('/child/<int:child_id>/exam-schedule')
@login_required
def child_exam_schedule(child_id):
    if current_user.role != 'parent':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    parent = Parent.query.filter_by(user_id=current_user.id).first()
    if not parent:
        flash('Parent profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Verify child belongs to parent
    child = Student.query.filter_by(id=child_id, parent_id=parent.id).first()
    if not child:
        flash('Child not found or access denied.', 'error')
        return redirect(url_for('parent.dashboard'))
    
    # Get exam schedule for child's grade
    exams = ExamSchedule.query.filter_by(grade=child.grade).order_by(ExamSchedule.exam_date).all()
    
    # Get child's exam assignments
    exam_assignments = ExamAssignment.query.filter_by(student_id=child.id).all()
    
    # Create a mapping of exam to assignment
    assignment_map = {assignment.exam_schedule_id: assignment for assignment in exam_assignments}
    
    return render_template('parent/child_exam_schedule.html',
                         exams=exams,
                         assignment_map=assignment_map,
                         child=child,
                         parent=parent)

@parent_bp.route('/child/<int:child_id>/seating-plan/<int:exam_id>')
@login_required
def child_seating_plan(child_id, exam_id):
    if current_user.role != 'parent':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    parent = Parent.query.filter_by(user_id=current_user.id).first()
    if not parent:
        flash('Parent profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Verify child belongs to parent
    child = Student.query.filter_by(id=child_id, parent_id=parent.id).first()
    if not child:
        flash('Child not found or access denied.', 'error')
        return redirect(url_for('parent.dashboard'))
    
    # Get exam details
    exam = ExamSchedule.query.get_or_404(exam_id)
    
    # Get child's assignment for this exam
    assignment = ExamAssignment.query.filter_by(
        student_id=child.id,
        exam_schedule_id=exam_id
    ).first()
    
    if not assignment:
        flash('No seating assignment found for this exam.', 'error')
        return redirect(url_for('parent.child_exam_schedule', child_id=child.id))
    
    # Get all assignments for this exam to show seating plan
    all_assignments = ExamAssignment.query.filter_by(exam_schedule_id=exam_id).all()
    
    # Group by room
    room_assignments = {}
    for assign in all_assignments:
        room_id = assign.room_id
        if room_id not in room_assignments:
            room_assignments[room_id] = []
        room_assignments[room_id].append(assign)
    
    return render_template('parent/child_seating_plan.html',
                         exam=exam,
                         assignment=assignment,
                         room_assignments=room_assignments,
                         child=child,
                         parent=parent)

@parent_bp.route('/child/<int:child_id>/attendance')
@login_required
def child_attendance(child_id):
    if current_user.role != 'parent':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    parent = Parent.query.filter_by(user_id=current_user.id).first()
    if not parent:
        flash('Parent profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Verify child belongs to parent
    child = Student.query.filter_by(id=child_id, parent_id=parent.id).first()
    if not child:
        flash('Child not found or access denied.', 'error')
        return redirect(url_for('parent.dashboard'))
    
    # Get attendance records
    subject_id = request.args.get('subject_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = Attendance.query.filter_by(student_id=child.id)
    
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    if start_date:
        query = query.filter(Attendance.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Attendance.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    
    attendance_records = query.order_by(Attendance.date.desc()).all()
    
    # Get subjects for filter
    from models import Subject
    subjects = Subject.query.filter_by(grade_level=child.grade).all()
    
    # Calculate attendance percentage
    total_classes = len(attendance_records)
    present_classes = len([r for r in attendance_records if r.status == 'Present'])
    attendance_percentage = (present_classes / total_classes * 100) if total_classes > 0 else 0
    
    return render_template('parent/child_attendance.html',
                         attendance_records=attendance_records,
                         subjects=subjects,
                         attendance_percentage=attendance_percentage,
                         child=child,
                         parent=parent)

@parent_bp.route('/child/<int:child_id>/profile')
@login_required
def child_profile(child_id):
    if current_user.role != 'parent':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    parent = Parent.query.filter_by(user_id=current_user.id).first()
    if not parent:
        flash('Parent profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Verify child belongs to parent
    child = Student.query.filter_by(id=child_id, parent_id=parent.id).first()
    if not child:
        flash('Child not found or access denied.', 'error')
        return redirect(url_for('parent.dashboard'))
    
    return render_template('parent/child_profile.html',
                         child=child,
                         parent=parent)

@parent_bp.route('/notifications')
@login_required
def notifications():
    if current_user.role != 'parent':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    parent = Parent.query.filter_by(user_id=current_user.id).first()
    if not parent:
        flash('Parent profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get notifications for parents
    from models import Notification
    notifications = Notification.query.filter(
        (Notification.recipient_type == 'parent') | 
        (Notification.recipient_type == 'all')
    ).order_by(Notification.created_at.desc()).all()
    
    return render_template('parent/notifications.html',
                         notifications=notifications,
                         parent=parent)

@parent_bp.route('/profile')
@login_required
def profile():
    if current_user.role != 'parent':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    parent = Parent.query.filter_by(user_id=current_user.id).first()
    if not parent:
        flash('Parent profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get parent's children
    children = Student.query.filter_by(parent_id=parent.id).all()
    
    return render_template('parent/profile.html',
                         parent=parent,
                         children=children)
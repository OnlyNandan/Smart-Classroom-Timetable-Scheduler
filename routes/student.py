"""
Student routes for Edu-Sync AI
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Student, TimetableEntry, ElectiveSelection, Subject, ExamSchedule, ExamAssignment
from datetime import datetime, date, timedelta

student_bp = Blueprint('student', __name__)

@student_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'student':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get student's timetable
    timetable_entries = TimetableEntry.query.filter_by(
        grade=student.grade, 
        section=student.section
    ).order_by(TimetableEntry.day_of_week, TimetableEntry.time_slot).all()
    
    # Get today's classes
    today = datetime.now().date()
    today_classes = [entry for entry in timetable_entries if entry.day_of_week == today.strftime('%A')]
    
    # Get upcoming exams
    upcoming_exams = ExamSchedule.query.filter(
        ExamSchedule.grade == student.grade,
        ExamSchedule.exam_date >= today
    ).order_by(ExamSchedule.exam_date).limit(5).all()
    
    # Get elective selections
    elective_selections = ElectiveSelection.query.filter_by(student_id=student.id).all()
    
    return render_template('student/dashboard.html',
                         student=student,
                         timetable_entries=timetable_entries,
                         today_classes=today_classes,
                         upcoming_exams=upcoming_exams,
                         elective_selections=elective_selections)

@student_bp.route('/timetable')
@login_required
def timetable():
    if current_user.role != 'student':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get student's timetable
    timetable_entries = TimetableEntry.query.filter_by(
        grade=student.grade, 
        section=student.section
    ).order_by(TimetableEntry.day_of_week, TimetableEntry.time_slot).all()
    
    # Group by day for easier display
    timetable_by_day = {}
    for entry in timetable_entries:
        day = entry.day_of_week
        if day not in timetable_by_day:
            timetable_by_day[day] = []
        timetable_by_day[day].append(entry)
    
    return render_template('student/timetable.html',
                         timetable_by_day=timetable_by_day,
                         student=student)

@student_bp.route('/electives', methods=['GET', 'POST'])
@login_required
def electives():
    if current_user.role != 'student':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    if request.method == 'POST':
        selected_subjects = request.form.getlist('elective_subjects')
        academic_year = request.form.get('academic_year')
        
        # Clear existing selections for this academic year
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
        flash('Elective selections submitted successfully!', 'success')
        return redirect(url_for('student.electives'))
    
    # Get available elective subjects for student's grade
    elective_subjects = Subject.query.filter_by(
        grade_level=student.grade,
        is_elective=True
    ).all()
    
    # Get current selections
    current_selections = ElectiveSelection.query.filter_by(student_id=student.id).all()
    
    return render_template('student/electives.html',
                         elective_subjects=elective_subjects,
                         current_selections=current_selections,
                         student=student)

@student_bp.route('/exam-schedule')
@login_required
def exam_schedule():
    if current_user.role != 'student':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get exam schedule for student's grade
    exams = ExamSchedule.query.filter_by(grade=student.grade).order_by(ExamSchedule.exam_date).all()
    
    # Get student's exam assignments
    exam_assignments = ExamAssignment.query.filter_by(student_id=student.id).all()
    
    # Create a mapping of exam to assignment
    assignment_map = {assignment.exam_schedule_id: assignment for assignment in exam_assignments}
    
    return render_template('student/exam_schedule.html',
                         exams=exams,
                         assignment_map=assignment_map,
                         student=student)

@student_bp.route('/seating-plan/<int:exam_id>')
@login_required
def seating_plan(exam_id):
    if current_user.role != 'student':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get exam details
    exam = ExamSchedule.query.get_or_404(exam_id)
    
    # Get student's assignment for this exam
    assignment = ExamAssignment.query.filter_by(
        student_id=student.id,
        exam_schedule_id=exam_id
    ).first()
    
    if not assignment:
        flash('No seating assignment found for this exam.', 'error')
        return redirect(url_for('student.exam_schedule'))
    
    # Get all assignments for this exam to show seating plan
    all_assignments = ExamAssignment.query.filter_by(exam_schedule_id=exam_id).all()
    
    # Group by room
    room_assignments = {}
    for assign in all_assignments:
        room_id = assign.room_id
        if room_id not in room_assignments:
            room_assignments[room_id] = []
        room_assignments[room_id].append(assign)
    
    return render_template('student/seating_plan.html',
                         exam=exam,
                         assignment=assignment,
                         room_assignments=room_assignments,
                         student=student)

@student_bp.route('/attendance')
@login_required
def attendance():
    if current_user.role != 'student':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get attendance records
    from models import Attendance
    
    subject_id = request.args.get('subject_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = Attendance.query.filter_by(student_id=student.id)
    
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    if start_date:
        query = query.filter(Attendance.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Attendance.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    
    attendance_records = query.order_by(Attendance.date.desc()).all()
    
    # Get subjects for filter
    subjects = Subject.query.filter_by(grade_level=student.grade).all()
    
    # Calculate attendance percentage
    total_classes = len(attendance_records)
    present_classes = len([r for r in attendance_records if r.status == 'Present'])
    attendance_percentage = (present_classes / total_classes * 100) if total_classes > 0 else 0
    
    return render_template('student/attendance.html',
                         attendance_records=attendance_records,
                         subjects=subjects,
                         attendance_percentage=attendance_percentage,
                         student=student)

@student_bp.route('/profile')
@login_required
def profile():
    if current_user.role != 'student':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    return render_template('student/profile.html', student=student)

@student_bp.route('/calendar')
@login_required
def calendar():
    if current_user.role != 'student':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get timetable entries for calendar view
    timetable_entries = TimetableEntry.query.filter_by(
        grade=student.grade, 
        section=student.section
    ).all()
    
    # Get exam schedule
    exams = ExamSchedule.query.filter_by(grade=student.grade).all()
    
    # Convert to calendar format
    calendar_events = []
    
    for entry in timetable_entries:
        calendar_events.append({
            'title': f"{entry.subject.name} - {entry.teacher.user.get_full_name()}",
            'start': f"{entry.day_of_week} {entry.time_slot}",
            'type': 'class',
            'subject': entry.subject.name,
            'teacher': entry.teacher.user.get_full_name(),
            'room': entry.room.room_number
        })
    
    for exam in exams:
        calendar_events.append({
            'title': f"Exam: {exam.subject.name}",
            'start': exam.exam_date.strftime('%Y-%m-%d'),
            'type': 'exam',
            'subject': exam.subject.name,
            'duration': f"{exam.duration_minutes} minutes"
        })
    
    return render_template('student/calendar.html',
                         calendar_events=calendar_events,
                         student=student)
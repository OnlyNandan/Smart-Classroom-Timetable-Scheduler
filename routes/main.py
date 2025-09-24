import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, session, g, flash, jsonify
from sqlalchemy import exc

from models import AppConfig, User, SchoolGroup, Grade, Stream, Subject, Semester, Department, Course, SystemMetric, ActivityLog, TimetableEntry
from extensions import db
from utils import hash_password, log_activity, calculate_growth, set_config
from werkzeug.security import check_password_hash

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    return redirect(url_for('main.dashboard'))

@main_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    try:
        if AppConfig.query.filter_by(key='setup_complete', value='true').first():
            return redirect(url_for('main.login'))
    except Exception:
        # This will fail if the table doesn't exist, which is expected on first run.
        # We let it proceed to the setup page.
        pass

    if request.method == 'POST':
        try:
            payload_str = request.form.get('payload')
            data = json.loads(payload_str)
            
            with db.session.begin_nested():
                admin_data = data['admin']
                admin_email = admin_data.get('email', f"{admin_data['username']}@example.com")
                admin = User(username=admin_data['username'], email=admin_email, password=hash_password(admin_data['password']), role='admin')
                db.session.add(admin)

                details = data['details']
                configs = [
                    AppConfig(key='app_mode', value=data['mode']),
                    AppConfig(key='institute_name', value=details['institute_name']),
                    AppConfig(key='working_days', value=json.dumps(details['working_days'])),
                    AppConfig(key='period_duration', value=details['period_duration']),
                    AppConfig(key='start_time', value=details['start_time']),
                    AppConfig(key='end_time', value=details['end_time']),
                    AppConfig(key='breaks', value=json.dumps(details['breaks']))
                ]
                db.session.add_all(configs)

                if data['mode'] == 'school':
                    for group_data in data['structure']:
                        new_group = SchoolGroup(name=group_data['name'])
                        db.session.add(new_group)
                        db.session.flush()
                        for grade_data in group_data['grades']:
                            db.session.add(Grade(name=grade_data['name'], group_id=new_group.id))
                        for stream_data in group_data['streams']:
                            new_stream = Stream(name=stream_data['name'], group_id=new_group.id)
                            db.session.add(new_stream)
                            db.session.flush()
                            for subject_data in stream_data['subjects']:
                                db.session.add(Subject(name=subject_data['name'], code=subject_data['code'], weekly_hours=subject_data['hours'], is_elective=subject_data['is_elective'], stream_id=new_stream.id))
                
                elif data['mode'] == 'college':
                    for sem_data in data['structure']:
                        new_sem = Semester(name=sem_data['name'])
                        db.session.add(new_sem)
                        db.session.flush()
                        for dept_data in sem_data['departments']:
                            new_dept = Department(name=dept_data['name'], semester_id=new_sem.id)
                            db.session.add(new_dept)
                            db.session.flush()
                            for course_data in dept_data['courses']:
                                db.session.add(Course(name=course_data['name'], code=course_data['code'], credits=course_data['credits'], course_type=course_data['type'], department_id=new_dept.id))
                
                db.session.add(AppConfig(key='setup_complete', value='true'))

            db.session.commit()
            log_activity('info', f"System setup completed for {details['institute_name']}.")
            
            db.session.add(SystemMetric(key='total_students', value=0))
            db.session.add(SystemMetric(key='total_teachers', value=0))
            db.session.add(SystemMetric(key='total_subjects', value=Subject.query.count() + Course.query.count()))
            db.session.add(SystemMetric(key='classes_scheduled', value=0))
            db.session.commit()
            
            flash('Setup complete! Please log in with your new admin account.', 'success')
            return jsonify({'status': 'success', 'redirect': url_for('main.login')})

        except Exception as e:
            db.session.rollback()
            print(f"ERROR during setup: {e}")
            return jsonify({'status': 'error', 'message': f'An unexpected error occurred: {e}. Please check the logs.'}), 500
            
    return render_template('setup.html')

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            log_activity('info', f"User '{user.username}' logged in.")
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')

@main_bp.route('/logout')
def logout():
    log_activity('info', f"User '{session.get('username')}' logged out.")
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.login'))

@main_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    # Get current statistics
    stats = {
        'teachers': User.query.filter_by(role='teacher').count(),
        'total_students': User.query.filter_by(role='student').count(),
        'classes_scheduled': TimetableEntry.query.count(),
    }
    if g.app_mode == 'school':
        stats['subjects'] = Subject.query.count()
    else:
        stats['subjects'] = Course.query.count()

    # Update system metrics for growth calculation
    today = datetime.now(timezone.utc).date()
    
    # Update or create metrics for today
    metrics_to_update = [
        ('total_students', stats['total_students']),
        ('total_teachers', stats['teachers']),
        ('total_subjects', stats['subjects']),
        ('classes_scheduled', stats['classes_scheduled'])
    ]
    
    for metric_key, current_value in metrics_to_update:
        existing_metric = SystemMetric.query.filter_by(key=metric_key, date=today).first()
        if existing_metric:
            existing_metric.value = current_value
        else:
            new_metric = SystemMetric(key=metric_key, value=current_value, date=today)
            db.session.add(new_metric)
    
    db.session.commit()

    # Calculate growth percentages
    stats['students_growth'] = calculate_growth('total_students', stats['total_students'])
    stats['teachers_growth'] = calculate_growth('total_teachers', stats['teachers'])
    stats['subjects_growth'] = calculate_growth('total_subjects', stats['subjects'])
    stats['scheduled_growth'] = calculate_growth('classes_scheduled', stats['classes_scheduled'])

    recent_activities = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(5).all()
    performance = {
        'accuracy': AppConfig.query.filter_by(key='last_schedule_accuracy').first(),
        'gen_time': AppConfig.query.filter_by(key='last_generation_time').first(),
    }
    performance['accuracy'] = float(performance['accuracy'].value) if performance['accuracy'] else 0
    performance['gen_time'] = float(performance['gen_time'].value) if performance['gen_time'] else 0
    performance['uptime'] = 99.9

    return render_template('dashboard.html', stats=stats, activities=recent_activities, performance=performance)

@main_bp.route('/api/dashboard-stats')
def get_dashboard_stats():
    """API endpoint for real-time dashboard statistics"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        # Get real-time statistics
        stats = {
            'teachers': User.query.filter_by(role='teacher').count(),
            'total_students': User.query.filter_by(role='student').count(),
            'classes_scheduled': TimetableEntry.query.count(),
        }
        if g.app_mode == 'school':
            stats['subjects'] = Subject.query.count()
        else:
            stats['subjects'] = Course.query.count()

        # Calculate growth percentages with fallback
        stats['students_growth'] = calculate_growth('total_students', stats['total_students']) or 0
        stats['teachers_growth'] = calculate_growth('total_teachers', stats['teachers']) or 0
        stats['subjects_growth'] = calculate_growth('total_subjects', stats['subjects']) or 0
        stats['scheduled_growth'] = calculate_growth('classes_scheduled', stats['classes_scheduled']) or 0

        # Get performance metrics
        accuracy_config = AppConfig.query.filter_by(key='last_schedule_accuracy').first()
        gen_time_config = AppConfig.query.filter_by(key='last_generation_time').first()
        
        performance = {
            'accuracy': float(accuracy_config.value) if accuracy_config else 95.0,
            'gen_time': float(gen_time_config.value) if gen_time_config else 2.5,
            'uptime': 99.9
        }
        
        return jsonify({
            'success': True,
            'stats': stats,
            'performance': performance,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

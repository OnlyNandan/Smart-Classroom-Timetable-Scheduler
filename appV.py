from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from init_db import (db, User, Teacher, Student, StudentGroup, Course, Room, CourseAssignment,
                     Holiday, Attendance, Substitution, TimetableRun, TimetableEntry, ManualLock)
from genetic_algorithm import run_class_timetable, detect_conflicts_for_run
from werkzeug.security import generate_password_hash, check_password_hash
import io, csv, pandas as pd, json
from datetime import datetime

app = Flask(__name__)
app.secret_key = "dev-secret"  # use env var in prod

#Db config

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:secretpassword@localhost:3306/timetabledb'  #conf with username:password@host:port/databasename
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        admin_user = User(
            username="admin",
            password=generate_password_hash("admin"),
            role="admin"
        )
        db.session.add(admin_user)
        db.session.commit()
# -------------------------
# Auth helpers (very minimal)
# -------------------------
def login_required(f):
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# -------------------------
# Basic routes: login / logout
# -------------------------
@app.route("/", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['role'] = user.role
            flash("Login successful", "success")
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            flash("Invalid credentials", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------------
# Admin Dashboard
# -------------------------
@app.route('/admin')
@login_required
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    teachers = Teacher.query.all()
    courses = Course.query.all()
    rooms = Room.query.all()
    groups = StudentGroup.query.all()
    runs = TimetableRun.query.order_by(TimetableRun.created_at.desc()).limit(10).all()
    return render_template('admin_dashboard.html', teachers=teachers, courses=courses, rooms=rooms, groups=groups, runs=runs)

# -------------------------
# Student Upload (CSV)
# -------------------------
@app.route('/admin/upload_students', methods=['POST'])
@login_required
def upload_students():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    f = request.files.get('file')
    if not f:
        flash("No file uploaded", "danger")
        return redirect(url_for('admin_dashboard'))
    stream = io.StringIO(f.stream.read().decode("utf-8"))
    reader = csv.DictReader(stream)
    for row in reader:
        s = Student(roll_no=row['roll_no'], name=row['name'], year=int(row.get('year',1)), branch=row.get('branch',''))
        db.session.add(s)
    db.session.commit()
    flash("Students uploaded", "success")
    return redirect(url_for('admin_dashboard'))

# -------------------------
# CourseAssignment endpoints (elective balancing helpers)
# -------------------------
@app.route('/admin/assign_course_group', methods=['POST'])
@login_required
def assign_course_group():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    course_id = int(request.form['course_id'])
    group_id = int(request.form['group_id'])
    seat_limit = request.form.get('seat_limit')
    ca = CourseAssignment(course_id=course_id, group_id=group_id, seat_limit=int(seat_limit) if seat_limit else None)
    db.session.add(ca)
    db.session.commit()
    flash("Assigned", "success")
    return redirect(url_for('admin_dashboard'))

# -------------------------
# Holidays
# -------------------------
@app.route('/admin/add_holiday', methods=['POST'])
@login_required
def add_holiday():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    d = request.form['date']
    name = request.form.get('name','')
    h = Holiday(date=datetime.strptime(d, "%Y-%m-%d").date(), name=name)
    db.session.add(h)
    db.session.commit()
    flash("Holiday added", "success")
    return redirect(url_for('admin_dashboard'))

# -------------------------
# Generate timetable route (class schedule)
# -------------------------
@app.route('/admin/generate_timetable', methods=['POST'])
@login_required
def generate_timetable():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    notes = request.form.get('notes','Generated by admin')
    res = run_class_timetable(run_notes=notes, created_by=session.get('user_id'))
    if not res.get('ok'):
        flash("Generation failed: see violations", "danger")
        return render_template('admin_dashboard.html', violations=res.get('violations'), teachers=Teacher.query.all(), courses=Course.query.all(), rooms=Room.query.all(), groups=StudentGroup.query.all(), runs=TimetableRun.query.order_by(TimetableRun.created_at.desc()).limit(10).all())
    flash(f"Timetable generated (run {res.get('run_id')}) saved {res.get('saved')} entries", "success")
    return redirect(url_for('view_run', run_id=res.get('run_id')))

# -------------------------
# Run viewer, diff & activate (historical comparison)
# -------------------------
@app.route('/runs')
@login_required
def runs():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    runs = TimetableRun.query.order_by(TimetableRun.created_at.desc()).all()
    return render_template('runs.html', runs=runs)

@app.route('/run/<int:run_id>')
@login_required
def view_run(run_id):
    run = TimetableRun.query.get_or_404(run_id)
    entries = TimetableEntry.query.filter_by(run_id=run_id).all()
    conflicts = detect_conflicts_for_run(run_id)
    return render_template('view_run.html', run=run, entries=entries, conflicts=conflicts)

# diff endpoint (simple JSON diff for front-end)
@app.route('/run/diff')
@login_required
def run_diff():
    left = int(request.args.get('left'))
    right = int(request.args.get('right'))
    left_entries = TimetableEntry.query.filter_by(run_id=left).all()
    right_entries = TimetableEntry.query.filter_by(run_id=right).all()
    # build mapping by (day,start_slot)
    def build_map(entries):
        m = {}
        for e in entries:
            m[(e.day, e.start_slot, e.duration, e.group_id)] = {"course": e.course_name, "teacher": e.teacher_name, "room": e.room_name}
        return m
    diff = {"left_only": [], "right_only": [], "changed": []}
    lm = build_map(left_entries)
    rm = build_map(right_entries)
    for k in set(list(lm.keys()) + list(rm.keys())):
        l = lm.get(k); r = rm.get(k)
        if l and not r:
            diff['left_only'].append({k: l})
        elif r and not l:
            diff['right_only'].append({k: r})
        elif l and r and l != r:
            diff['changed'].append({k: {"left": l, "right": r}})
    return jsonify(diff)

# -------------------------
# Drag-and-drop edit API (manual override)
# -------------------------
@app.route('/api/timetable/entry/<int:entry_id>/move', methods=['POST'])
@login_required
def move_entry(entry_id):
    entry = TimetableEntry.query.get_or_404(entry_id)
    data = request.get_json()
    # Validate: ensure target slots free for teacher/group/room and not locked
    # Simple validator (improve for atomic checks)
    new_day = data.get('day')
    new_start = int(data.get('start_slot'))
    new_duration = int(data.get('duration', entry.duration))
    # check manual lock
    if ManualLock.query.filter_by(entry_id=entry.id).first():
        return jsonify({"ok": False, "error": "Entry locked and cannot be moved."}), 400
    # conflict checks
    for s in range(new_start, new_start + new_duration):
        if TimetableEntry.query.filter(TimetableEntry.id != entry.id, TimetableEntry.day == new_day, TimetableEntry.start_slot <= s, (TimetableEntry.start_slot + TimetableEntry.duration - 1) >= s).first():
            return jsonify({"ok": False, "error": "Conflict at slot"}), 400
    # if okay, update and optionally create ManualLock
    entry.day = new_day
    entry.start_slot = new_start
    entry.duration = new_duration
    db.session.commit()
    # create lock if requested
    if data.get('lock', False):
        ml = ManualLock(entry_id=entry.id, locked_by=session.get('user_id'))
        db.session.add(ml)
        db.session.commit()
    return jsonify({"ok": True})

# -------------------------
# Exports (Excel)
# -------------------------
@app.route('/export/run/<int:run_id>/xlsx')
@login_required
def export_run_xlsx(run_id):
    entries = TimetableEntry.query.filter_by(run_id=run_id).all()
    rows = []
    for e in entries:
        rows.append({
            "Day": e.day, "Start": e.start_slot, "Duration": e.duration,
            "Course": e.course_name, "Teacher": e.teacher_name,
            "Room": e.room_name, "Group": e.group_name
        })
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return send_file(buf, download_name=f"timetable_run_{run_id}.xlsx", as_attachment=True)

# -------------------------
# Notification stub (send emails to teachers/students)
# -------------------------
def notify_users_on_run(run_id):
    # implement with Flask-Mail / external provider
    # get all teachers in run and send email + ICS
    pass

# -------------------------
# Teacher/Student dashboards skeletons
# -------------------------
@app.route('/teacher')
@login_required
def teacher_dashboard():
    if session.get('role') != 'teacher':
        return redirect(url_for('login'))
    # show latest run timetable for this teacher
    tid = session.get('user_id')
    latest_run = TimetableRun.query.order_by(TimetableRun.created_at.desc()).first()
    entries = TimetableEntry.query.filter_by(run_id=latest_run.id, teacher_id=tid).all() if latest_run else []
    return render_template('teacher_dashboard.html', entries=entries)

@app.route('/student')
@login_required
def student_dashboard():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    sid = session.get('user_id')
    student = Student.query.get(sid)
    latest_run = TimetableRun.query.order_by(TimetableRun.created_at.desc()).first()
    entries = TimetableEntry.query.filter_by(run_id=latest_run.id, group_id=student.group_id).all() if latest_run else []
    return render_template('student_dashboard.html', entries=entries)

# -------------------------
# Quick conflict-check API for current run
# -------------------------
@app.route('/api/run/<int:run_id>/conflicts')
@login_required
def run_conflicts(run_id):
    violations = detect_conflicts_for_run(run_id)
    return jsonify({"violations": violations})

if __name__ == '__main__':
    app.run(debug=True, ssl_context='adhoc')

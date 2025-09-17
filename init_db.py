from app import app, db, User, Course, Teacher, Classroom, StudentSection, TimetableEntry, hash_password

def create_initial_data():
    """
    Creates tables and populates them with initial master data.
    Safe to run multiple times (idempotent).
    """
    with app.app_context():
        print("Creating database tables...")
        db.create_all()

        # --- Create Users ---
        if not User.query.filter_by(username='admin').first():
            print("Creating default admin user...")
            db.session.add(User(username='admin', password=hash_password('admin'), role='admin'))

        if not User.query.filter_by(username='teacher_jane').first():
            print("Creating default teacher user...")
            db.session.add(User(username='teacher_jane', password=hash_password('password'), role='teacher'))

        # --- Create Master Data ---
        if Course.query.count() == 0:
            print("Populating Courses...")
            db.session.add_all([
                Course(course_id="CSE301", course_name="Data Structures", weekly_hours=4, reqd_lab=True, lab_hours=2),
                Course(course_id="CSE302", course_name="DBMS", weekly_hours=4, reqd_lab=True, lab_hours=2),
                Course(course_id="CSE303", course_name="Computer Organization", weekly_hours=3, reqd_lab=False, lab_hours=0),
                Course(course_id="CSE304", course_name="Operating Systems", weekly_hours=4, reqd_lab=True, lab_hours=2),
                Course(course_id="MTH201", course_name="Discrete Mathematics", weekly_hours=3, reqd_lab=False, lab_hours=0),
            ])

        if Teacher.query.count() == 0:
            print("Populating Teachers...")
            db.session.add_all([
                Teacher(teacher_id="T101", teacher_name="Dr. Ramesh Kumar", handling_subject="CSE301", max_hours_week=12),
                Teacher(teacher_id="T102", teacher_name="Prof. Meena", handling_subject="CSE302", max_hours_week=12),
                Teacher(teacher_id="T103", teacher_name="Dr. Ajay Nair", handling_subject="CSE303", max_hours_week=10),
                Teacher(teacher_id="T104", teacher_name="Prof. Kavita Rao", handling_subject="CSE304", max_hours_week=12),
                Teacher(teacher_id="T105", teacher_name="Dr. Sunil Verma", handling_subject="MTH201", max_hours_week=8),
            ])

        if Classroom.query.count() == 0:
            print("Populating Classrooms...")
            db.session.add_all([
                Classroom(room_id="R101", type="Classroom", capacity=60),
                Classroom(room_id="R102", type="Classroom", capacity=60),
                Classroom(room_id="LabC1", type="Lab", capacity=30),
                Classroom(room_id="LabD2", type="Lab", capacity=30),
            ])

        if StudentSection.query.count() == 0:
            print("Populating Student Sections...")
            db.session.add_all([
                StudentSection(section_id="SEC3A", no_of_students=55, assigned_classroom="R101"),
                StudentSection(section_id="SEC3B", no_of_students=50, assigned_classroom="R102"),
            ])

        # Clear any old timetable data
        if TimetableEntry.query.count() > 0:
            print("Clearing old timetable entries...")
            db.session.query(TimetableEntry).delete()

        try:
            db.session.commit()
            print("✅ Database initialization complete.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ An error occurred: {e}")

if __name__ == '__main__':
    create_initial_data()

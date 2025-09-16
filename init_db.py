from app import app, db, User, Course, Teacher, Classroom, StudentGroup, TimetableEntry, hash_password

def create_initial_data():
    """
    Creates tables and populates them with initial master data.
    It's safe to run multiple times.
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
                Course(name="Intro to AI", code="CS401", credit_hours=3, lab_required=True),
                Course(name="Advanced Algorithms", code="CS301", credit_hours=4, lab_required=True),
                Course(name="Modern Databases", code="DB305", credit_hours=3, lab_required=False),
                Course(name="UI/UX Design", code="DS202", credit_hours=3, lab_required=True),
            ])
        
        if Teacher.query.count() == 0:
            print("Populating Teachers...")
            db.session.add_all([
                Teacher(name="Dr. Evelyn Reed", contact="e.reed@college.edu"),
                Teacher(name="Prof. Samuel Carter", contact="s.carter@college.edu"),
                Teacher(name="Jane Doe", contact="jane.doe@college.edu"),
            ])

        if Classroom.query.count() == 0:
            print("Populating Classrooms...")
            db.session.add_all([
                Classroom(room_number="A-101", capacity=50, has_projector=True, is_lab=False),
                Classroom(room_number="B-203", capacity=30, has_projector=True, is_lab=False),
                Classroom(room_number="Lab-C1", capacity=25, has_projector=True, is_lab=True),
                Classroom(room_number="Lab-D2", capacity=25, has_projector=False, is_lab=True),
            ])
        
        if StudentGroup.query.count() == 0:
            print("Populating Student Groups...")
            db.session.add_all([
                StudentGroup(name="CS Year 3, Section A"),
                StudentGroup(name="CS Year 3, Section B"),
                StudentGroup(name="Design Year 2, Section A"),
            ])
        
        # Clear any old timetable data
        if TimetableEntry.query.count() > 0:
            print("Clearing old timetable entries...")
            db.session.query(TimetableEntry).delete()

        try:
            db.session.commit()
            print("Database initialization complete.")
        except Exception as e:
            db.session.rollback()
            print(f"An error occurred: {e}")

if __name__ == '__main__':
    create_initial_data()


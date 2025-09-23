import os
import sys
from app import app, db, User, Grade, Course, Teacher, Classroom, StudentSection, TimetableEntry, hash_password, AppConfig

def clear_data():
    """Drops all tables, recreates them, and clears the session."""
    with app.app_context():
        print("Clearing all database tables...")
        db.session.remove()
        db.drop_all()
        db.create_all()
        print("Tables cleared and recreated.")

def create_school_data():
    """Populates the database with sample data for a school environment."""
    with app.app_context():
        print("Creating school sample data...")

        # --- Set App Configuration ---
        db.session.add(AppConfig(key='app_mode', value='school'))

        # --- Create Users ---
        db.session.add(User(username='admin', password=hash_password('admin'), role='admin'))
        db.session.add(User(username='teacher_jane', password=hash_password('password'), role='teacher'))

        # --- Create Grades ---
        grades_list = [
            Grade(name='Grade 1', is_static_classroom=True), Grade(name='Grade 2', is_static_classroom=True),
            Grade(name='Grade 3', is_static_classroom=True), Grade(name='Grade 4', is_static_classroom=True),
            Grade(name='Grade 5', is_static_classroom=True), Grade(name='Grade 6', is_static_classroom=False),
            Grade(name='Grade 7', is_static_classroom=False), Grade(name='Grade 8', is_static_classroom=False),
            Grade(name='Grade 9', is_static_classroom=False), Grade(name='Grade 10', is_static_classroom=False),
            Grade(name='Grade 11', is_static_classroom=False), Grade(name='Grade 12', is_static_classroom=False)
        ]
        db.session.add_all(grades_list)
        db.session.commit()
        grades = {g.name: g for g in Grade.query.all()}

        # --- Create Courses ---
        courses_list = [
            Course(course_id="G1_MTH", course_name="Math Grade 1", weekly_hours=5, grade_id=grades['Grade 1'].id),
            Course(course_id="G1_ENG", course_name="English Grade 1", weekly_hours=5, grade_id=grades['Grade 1'].id),
            Course(course_id="G5_SCI", course_name="Science Grade 5", weekly_hours=4, grade_id=grades['Grade 5'].id),
            Course(course_id="G5_SOC", course_name="Social Studies Grade 5", weekly_hours=3, grade_id=grades['Grade 5'].id),
            Course(course_id="G9_ALG", course_name="Algebra", weekly_hours=5, grade_id=grades['Grade 9'].id),
            Course(course_id="G9_PHY", course_name="Physics", weekly_hours=4, grade_id=grades['Grade 9'].id),
            Course(course_id="G12_CAL", course_name="Calculus", weekly_hours=5, grade_id=grades['Grade 12'].id),
            Course(course_id="G12_LIT", course_name="Literature", weekly_hours=4, grade_id=grades['Grade 12'].id),
        ]
        db.session.add_all(courses_list)
        db.session.commit()
        courses = {c.course_id: c for c in Course.query.all()}

        # --- Create Teachers ---
        t1 = Teacher(teacher_id="T101", teacher_name="Alice Johnson", max_hours_week=20)
        t1.grades = [grades['Grade 1'], grades['Grade 2'], grades['Grade 3']]
        t1.courses = [courses['G1_MTH'], courses['G1_ENG']]
        
        t2 = Teacher(teacher_id="T102", teacher_name="Bob Williams", max_hours_week=18)
        t2.grades = [grades['Grade 4'], grades['Grade 5']]
        t2.courses = [courses['G5_SCI'], courses['G5_SOC']]

        t3 = Teacher(teacher_id="T103", teacher_name="Charles Brown", max_hours_week=15)
        t3.grades = [grades['Grade 9'], grades['Grade 10']]
        t3.courses = [courses['G9_ALG'], courses['G9_PHY']]
        
        t4 = Teacher(teacher_id="T104", teacher_name="Diana Miller", max_hours_week=12)
        t4.grades = [grades['Grade 11'], grades['Grade 12']]
        t4.courses = [courses['G12_CAL'], courses['G12_LIT']]
        db.session.add_all([t1, t2, t3, t4])

        # --- Create Classrooms ---
        db.session.add_all([
            Classroom(room_id="R101", type="Classroom", capacity=30), Classroom(room_id="R102", type="Classroom", capacity=30),
            Classroom(room_id="R201", type="Classroom", capacity=35), Classroom(room_id="R202", type="Classroom", capacity=35),
            Classroom(room_id="SciLabA", type="Lab", capacity=40), Classroom(room_id="SciLabB", type="Lab", capacity=40),
        ])

        # --- Create Student Sections ---
        db.session.add_all([
            StudentSection(section_id="G1A", no_of_students=28, grade_id=grades['Grade 1'].id, assigned_classroom_id="R101"),
            StudentSection(section_id="G5B", no_of_students=32, grade_id=grades['Grade 5'].id, assigned_classroom_id="R201"),
            StudentSection(section_id="G9A", no_of_students=30, grade_id=grades['Grade 9'].id),
            StudentSection(section_id="G12C", no_of_students=25, grade_id=grades['Grade 12'].id),
        ])
        
        db.session.commit()
        print("✅ School sample data created successfully.")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'clear':
        clear_data()
    else:
        # Default action: clear everything and set up with school data.
        clear_data()
        create_school_data()


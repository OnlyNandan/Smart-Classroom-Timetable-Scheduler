#!/usr/bin/env python3
"""
Realistic Database Initialization Script
Creates a more realistic school/college structure with proper subject-department relationships
"""

import os
import sys
from faker import Faker
import random
from datetime import datetime, time

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, User, Teacher, Student, StudentSection, Department, Semester, Course, Subject, Classroom, TimetableEntry, Grade, SchoolGroup, Stream, Exam, ExamSeating, AppConfig
from werkzeug.security import generate_password_hash

fake = Faker()

def clear_database():
    """Clear all existing data"""
    print("🧹 Clearing existing database...")
    
    # Delete in correct order to avoid foreign key constraints
    try:
        # First delete all timetable entries
        db.session.query(TimetableEntry).delete()
        db.session.commit()
        
        # Delete exam related data
        db.session.query(ExamSeating).delete()
        db.session.query(Exam).delete()
        db.session.commit()
        
        # Delete students
        db.session.query(Student).delete()
        db.session.commit()
        
        # Delete teacher-course associations first
        db.session.execute("DELETE FROM teacher_college_courses")
        db.session.execute("DELETE FROM teacher_school_subjects")
        db.session.commit()
        
        # Delete teachers
        db.session.query(Teacher).delete()
        db.session.commit()
        
        # Delete sections
        db.session.query(StudentSection).delete()
        db.session.commit()
        
        # Delete classrooms
        db.session.query(Classroom).delete()
        db.session.commit()
        
        # Delete subjects
        db.session.query(Subject).delete()
        db.session.commit()
        
        # Delete courses
        db.session.query(Course).delete()
        db.session.commit()
        
        # Delete streams
        db.session.query(Stream).delete()
        db.session.commit()
        
        # Delete grades
        db.session.query(Grade).delete()
        db.session.commit()
        
        # Delete departments
        db.session.query(Department).delete()
        db.session.commit()
        
        # Delete semesters
        db.session.query(Semester).delete()
        db.session.commit()
        
        # Delete school groups
        db.session.query(SchoolGroup).delete()
        db.session.commit()
        
        # Delete users last
        db.session.query(User).delete()
        db.session.commit()
        
        print("✅ Database cleared")
        
    except Exception as e:
        print(f"⚠️ Error clearing database: {e}")
        db.session.rollback()
        # Try alternative approach - drop and recreate tables
        print("🔄 Trying alternative approach...")
        db.drop_all()
        db.create_all()
        print("✅ Database recreated")

def create_realistic_data():
    """Create realistic school/college data"""
    print("🏗️ Creating realistic data...")
    
    # Create school group
    school_group = SchoolGroup(name="RV College of Engineering")
    db.session.add(school_group)
    db.session.flush()
    
    # Create semesters
    semesters = []
    for i in range(1, 9):  # 8 semesters
        semester = Semester(name=f"SEM {i}")
        db.session.add(semester)
        semesters.append(semester)
    db.session.flush()
    
    # Create departments with realistic names
    department_names = [
        "Computer Science Engineering",
        "Electronics and Communication Engineering", 
        "Information Technology",
        "Mechanical Engineering",
        "Civil Engineering",
        "Electrical Engineering",
        "Aerospace Engineering",
        "Chemical Engineering"
    ]
    
    departments = []
    for i, name in enumerate(department_names):
        # Assign each department to 2 semesters
        semester_id = semesters[i % len(semesters)].id
        dept = Department(name=name, semester_id=semester_id)
        db.session.add(dept)
        departments.append(dept)
    db.session.flush()
    
    # Create realistic subjects for each department
    subjects_data = {
        "Computer Science Engineering": [
            ("Data Structures", "CSE_DS101", 4, False),
            ("Algorithms", "CSE_ALG102", 4, False),
            ("Object Oriented Programming", "CSE_OOP103", 3, False),
            ("Database Management Systems", "CSE_DBMS201", 4, False),
            ("Operating Systems", "CSE_OS202", 4, False),
            ("Computer Networks", "CSE_CN203", 3, False),
            ("Software Engineering", "CSE_SE301", 3, False),
            ("Machine Learning", "CSE_ML302", 3, False),
            ("Artificial Intelligence", "CSE_AI303", 3, False),
            ("Web Development", "CSE_WD401", 3, True),
            ("Mobile App Development", "CSE_MAD402", 3, True)
        ],
        "Electronics and Communication Engineering": [
            ("Digital Electronics", "ECE_DE101", 4, False),
            ("Analog Electronics", "ECE_AE102", 4, False),
            ("Signals and Systems", "ECE_SS103", 4, False),
            ("Communication Systems", "ECE_CS201", 4, False),
            ("Microprocessors", "ECE_MP202", 3, False),
            ("VLSI Design", "ECE_VLSI203", 3, False),
            ("Embedded Systems", "ECE_ES301", 3, False),
            ("Digital Signal Processing", "ECE_DSP302", 3, False),
            ("Wireless Communication", "ECE_WC303", 3, False),
            ("IoT Development", "ECE_IOT401", 3, True),
            ("Robotics", "ECE_ROB402", 3, True)
        ],
        "Information Technology": [
            ("Programming Fundamentals", "IT_PF101", 4, False),
            ("Data Structures and Algorithms", "IT_DSA102", 4, False),
            ("Database Systems", "IT_DBS103", 4, False),
            ("Web Technologies", "IT_WT201", 3, False),
            ("Software Testing", "IT_ST202", 3, False),
            ("Computer Networks", "IT_CN203", 3, False),
            ("Information Security", "IT_IS301", 3, False),
            ("Cloud Computing", "IT_CC302", 3, False),
            ("Big Data Analytics", "IT_BDA303", 3, False),
            ("DevOps", "IT_DO401", 3, True),
            ("Blockchain Technology", "IT_BT402", 3, True)
        ],
        "Mechanical Engineering": [
            ("Engineering Mechanics", "ME_EM101", 4, False),
            ("Thermodynamics", "ME_TD102", 4, False),
            ("Fluid Mechanics", "ME_FM103", 4, False),
            ("Machine Design", "ME_MD201", 4, False),
            ("Manufacturing Processes", "ME_MP202", 3, False),
            ("Heat Transfer", "ME_HT203", 3, False),
            ("Automotive Engineering", "ME_AE301", 3, False),
            ("CAD/CAM", "ME_CAD302", 3, False),
            ("Robotics and Automation", "ME_RA303", 3, False),
            ("Renewable Energy", "ME_RE401", 3, True),
            ("Aerospace Engineering", "ME_ASE402", 3, True)
        ],
        "Civil Engineering": [
            ("Structural Analysis", "CE_SA101", 4, False),
            ("Concrete Technology", "CE_CT102", 4, False),
            ("Soil Mechanics", "CE_SM103", 4, False),
            ("Transportation Engineering", "CE_TE201", 3, False),
            ("Environmental Engineering", "CE_EE202", 3, False),
            ("Water Resources", "CE_WR203", 3, False),
            ("Construction Management", "CE_CM301", 3, False),
            ("Geotechnical Engineering", "CE_GE302", 3, False),
            ("Urban Planning", "CE_UP303", 3, False),
            ("Sustainable Construction", "CE_SC401", 3, True),
            ("Smart Cities", "CE_SC402", 3, True)
        ],
        "Electrical Engineering": [
            ("Circuit Analysis", "EE_CA101", 4, False),
            ("Electromagnetic Fields", "EE_EMF102", 4, False),
            ("Power Systems", "EE_PS103", 4, False),
            ("Control Systems", "EE_CS201", 3, False),
            ("Electrical Machines", "EE_EM202", 3, False),
            ("Power Electronics", "EE_PE203", 3, False),
            ("Renewable Energy Systems", "EE_RES301", 3, False),
            ("Smart Grid", "EE_SG302", 3, False),
            ("Electric Vehicles", "EE_EV303", 3, False),
            ("IoT in Power Systems", "EE_IOT401", 3, True),
            ("Energy Storage", "EE_ES402", 3, True)
        ],
        "Aerospace Engineering": [
            ("Aerodynamics", "AE_AD101", 4, False),
            ("Flight Mechanics", "AE_FM102", 4, False),
            ("Aircraft Structures", "AE_AS103", 4, False),
            ("Propulsion Systems", "AE_PS201", 3, False),
            ("Aircraft Design", "AE_AD202", 3, False),
            ("Space Technology", "AE_ST203", 3, False),
            ("Avionics", "AE_AV301", 3, False),
            ("Aircraft Maintenance", "AE_AM302", 3, False),
            ("Unmanned Aerial Vehicles", "AE_UAV303", 3, False),
            ("Space Exploration", "AE_SE401", 3, True),
            ("Satellite Technology", "AE_ST402", 3, True)
        ],
        "Chemical Engineering": [
            ("Chemical Process Calculations", "CHE_CPC101", 4, False),
            ("Thermodynamics", "CHE_TD102", 4, False),
            ("Mass Transfer", "CHE_MT103", 4, False),
            ("Heat Transfer", "CHE_HT201", 3, False),
            ("Chemical Reaction Engineering", "CHE_CRE202", 3, False),
            ("Process Control", "CHE_PC203", 3, False),
            ("Petroleum Engineering", "CHE_PE301", 3, False),
            ("Biochemical Engineering", "CHE_BE302", 3, False),
            ("Environmental Engineering", "CHE_EE303", 3, False),
            ("Pharmaceutical Engineering", "CHE_PE401", 3, True),
            ("Green Chemistry", "CHE_GC402", 3, True)
        ]
    }
    
    # Create subjects for each department
    subjects = []
    for dept in departments:
        dept_name = dept.name
        if dept_name in subjects_data:
            for subject_name, code, hours, is_elective in subjects_data[dept_name]:
                # Create stream for this department
                stream = Stream(name=f"{dept_name} Stream", group_id=school_group.id)
                db.session.add(stream)
                db.session.flush()
                
                subject = Subject(
                    name=subject_name,
                    code=code,
                    weekly_hours=hours,
                    is_elective=is_elective,
                    stream_id=stream.id
                )
                db.session.add(subject)
                subjects.append(subject)
    
    db.session.flush()
    
    # Create courses for each department
    courses = []
    for dept in departments:
        dept_name = dept.name
        if dept_name in subjects_data:
            for subject_name, code, hours, is_elective in subjects_data[dept_name]:
                course = Course(
                    name=subject_name,
                    code=code,
                    credits=hours,
                    course_type="Core" if not is_elective else "Elective",
                    department_id=dept.id
                )
                db.session.add(course)
                courses.append(course)
    
    db.session.flush()
    
    # Create grades
    grades = []
    for i in range(1, 9):  # 8 grades
        grade = Grade(name=f"Grade {i}", group_id=school_group.id)
        db.session.add(grade)
        grades.append(grade)
    db.session.flush()
    
    # Create sections for each department
    sections = []
    for dept in departments:
        for section_letter in ['A', 'B', 'C', 'D', 'E']:
            section = StudentSection(
                name=f"Section {section_letter}",
                capacity=30,
                grade_id=grades[dept.id % len(grades)].id,
                department_id=dept.id
            )
            db.session.add(section)
            sections.append(section)
    
    db.session.flush()
    
    # Create classrooms
    classrooms = []
    building_names = ['A', 'B', 'C', 'D', 'E']
    for building in building_names:
        for floor in range(1, 4):
            for room in range(1, 6):
                room_id = f"{building}{floor}{room:02d}"
                capacity = random.randint(25, 50)
                features = random.choice([
                    "Projector, Whiteboard, AC",
                    "Smart Board, Projector, AC",
                    "Whiteboard, AC",
                    "Projector, Whiteboard",
                    "Smart Board, AC"
                ])
                
                classroom = Classroom(
                    room_id=room_id,
                    capacity=capacity,
                    features=features
                )
                db.session.add(classroom)
                classrooms.append(classroom)
    
    db.session.flush()
    
    # Create users and teachers
    teachers = []
    for i in range(50):  # 50 teachers
        user = User(
            username=f"teacher{i+1:02d}",
            email=f"teacher{i+1:02d}@rvc.edu",
            password="teacher123",  # Simple password for testing
            role="teacher"
        )
        db.session.add(user)
        db.session.flush()
        
        teacher = Teacher(
            user_id=user.id,
            full_name=fake.name(),
            max_weekly_hours=random.randint(20, 30)
        )
        db.session.add(teacher)
        teachers.append(teacher)
    
    db.session.flush()
    
    # Assign teachers to courses (ensure proper subject-department matching)
    teacher_course_assignments = []
    for course in courses:
        # Find teachers who can teach this course (random assignment for now)
        available_teachers = [t for t in teachers if len([tc for tc in teacher_course_assignments if tc[0] == t.id]) < 5]
        if available_teachers:
            teacher = random.choice(available_teachers)
            teacher_course_assignments.append((teacher.id, course.id))
    
    # Create students
    students = []
    for i in range(500):  # 500 students
        user = User(
            username=f"student{i+1:03d}",
            email=f"student{i+1:03d}@rvc.edu",
            password="student123",  # Simple password for testing
            role="student"
        )
        db.session.add(user)
        db.session.flush()
        
        # Assign student to a random section
        section = random.choice(sections)
        student = Student(
            user_id=user.id,
            full_name=fake.name(),
            section_id=section.id
        )
        db.session.add(student)
        students.append(student)
    
    db.session.flush()
    
    # Create admin user
    admin_user = User(
        username="admin",
        email="admin@rvc.edu",
        password="admin123",  # Simple password for testing
        role="admin"
    )
    db.session.add(admin_user)
    
    # Add AppConfig
    configs = [
        ('app_name', 'RV College of Engineering'),
        ('app_mode', 'college'),
        ('working_days', '["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]'),
        ('start_time', '09:00'),
        ('end_time', '17:00'),
        ('period_duration', '60'),
        ('break_duration', '30'),
        ('max_classes_per_day', '8'),
        ('setup_completed', 'true')
    ]
    
    for key, value in configs:
        config = AppConfig(key=key, value=value)
        db.session.add(config)
    
    db.session.commit()
    
    print(f"✅ Created realistic data:")
    print(f"   📚 Semesters: {len(semesters)}")
    print(f"   🏢 Departments: {len(departments)}")
    print(f"   📖 Subjects: {len(subjects)}")
    print(f"   📚 Courses: {len(courses)}")
    print(f"   👥 Sections: {len(sections)}")
    print(f"   🏫 Classrooms: {len(classrooms)}")
    print(f"   👨‍🏫 Teachers: {len(teachers)}")
    print(f"   👨‍🎓 Students: {len(students)}")
    
    return {
        'semesters': semesters,
        'departments': departments,
        'subjects': subjects,
        'courses': courses,
        'sections': sections,
        'classrooms': classrooms,
        'teachers': teachers,
        'students': students
    }

def main():
    """Main function to initialize the database"""
    app = create_app()
    
    with app.app_context():
        try:
            clear_database()
            data = create_realistic_data()
            print("\n🎉 Database initialization completed successfully!")
            print("\n📋 Login credentials:")
            print("   Admin: admin / admin123")
            print("   Teachers: teacher01-teacher50 / teacher123")
            print("   Students: student001-student500 / student123")
            
        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    main()

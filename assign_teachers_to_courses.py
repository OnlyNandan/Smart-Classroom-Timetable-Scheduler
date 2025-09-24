#!/usr/bin/env python3
"""
Assign teachers to courses for timetable generation
"""

import os
import sys
import random
from sqlalchemy import text

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, Teacher, Course, Department

def assign_teachers_to_courses():
    """Assign teachers to courses based on department"""
    app = create_app()
    
    with app.app_context():
        print("🎯 Assigning teachers to courses...")
        
        # Get all teachers and courses
        teachers = Teacher.query.all()
        courses = Course.query.all()
        
        print(f"👨‍🏫 Found {len(teachers)} teachers")
        print(f"📚 Found {len(courses)} courses")
        
        # Group courses by department
        courses_by_dept = {}
        for course in courses:
            if course.department_id not in courses_by_dept:
                courses_by_dept[course.department_id] = []
            courses_by_dept[course.department_id].append(course)
        
        print(f"🏢 Found {len(courses_by_dept)} departments with courses")
        
        # Assign teachers to courses
        assignments = []
        for dept_id, dept_courses in courses_by_dept.items():
            print(f"\n📖 Department {dept_id}: {len(dept_courses)} courses")
            
            # Get available teachers (not assigned to too many courses)
            available_teachers = [t for t in teachers if len(assignments) < 5 or 
                                len([a for a in assignments if a[0] == t.id]) < 5]
            
            if not available_teachers:
                print("⚠️ No available teachers")
                continue
            
            # Assign each course to a teacher
            for course in dept_courses:
                teacher = random.choice(available_teachers)
                assignments.append((teacher.id, course.id))
                print(f"  ✅ {teacher.full_name} -> {course.name}")
        
        # Insert assignments into database
        if assignments:
            print(f"\n💾 Inserting {len(assignments)} teacher-course assignments...")
            
            # Clear existing assignments
            db.session.execute(text("DELETE FROM teacher_college_courses"))
            db.session.commit()
            
            # Insert new assignments
            for teacher_id, course_id in assignments:
                db.session.execute(text(
                    "INSERT INTO teacher_college_courses (teacher_id, course_id) VALUES (:teacher_id, :course_id)"
                ), {"teacher_id": teacher_id, "course_id": course_id})
            
            db.session.commit()
            print("✅ Teacher-course assignments completed!")
        else:
            print("❌ No assignments created")

if __name__ == "__main__":
    assign_teachers_to_courses()

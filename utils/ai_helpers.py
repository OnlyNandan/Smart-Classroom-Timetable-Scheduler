"""
AI Helper utilities for Edu-Sync AI
Gemini AI integration for timetable generation, exam scheduling, and repair
"""

import google.generativeai as genai
import json
from datetime import datetime, timedelta
from models import db, Teacher, Student, Subject, Room, TimetableEntry, ExamSchedule, ExamAssignment
import os

class AIHelper:
    def __init__(self):
        """Initialize AI helper with Gemini configuration"""
        self.model = genai.GenerativeModel('gemini-pro')
        self.generation_config = {
            "temperature": 0.1,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 8192,
        }
    
    def generate_timetable(self):
        """Generate optimal timetable using AI"""
        try:
            # Collect data for AI
            ai_data = self._prepare_timetable_data()
            
            # Load AI prompt
            prompt = self._load_timetable_prompt()
            
            # Format prompt with data
            formatted_prompt = prompt.format(json_data=json.dumps(ai_data, indent=2))
            
            # Generate response
            response = self.model.generate_content(
                formatted_prompt,
                generation_config=self.generation_config
            )
            
            # Parse AI response
            ai_timetable = json.loads(response.text)
            
            # Save generated timetable
            version_name = f"AI_Generated_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self._save_timetable(ai_timetable, version_name)
            
            return {
                'success': True,
                'version': version_name,
                'entries_count': len(ai_timetable)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_exam_schedule(self):
        """Generate exam schedule and seating plan using AI"""
        try:
            # Collect data for AI
            ai_data = self._prepare_exam_data()
            
            # Load AI prompt
            prompt = self._load_exam_prompt()
            
            # Format prompt with data
            formatted_prompt = prompt.format(json_data=json.dumps(ai_data, indent=2))
            
            # Generate response
            response = self.model.generate_content(
                formatted_prompt,
                generation_config=self.generation_config
            )
            
            # Parse AI response
            ai_schedule = json.loads(response.text)
            
            # Save exam schedule
            self._save_exam_schedule(ai_schedule)
            
            return {
                'success': True,
                'exams_count': len(ai_schedule.get('exam_schedule', [])),
                'seating_plans_count': len(ai_schedule.get('seating_plan', []))
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def repair_timetable(self):
        """Repair timetable conflicts using AI"""
        try:
            # Get current timetable
            timetable_entries = TimetableEntry.query.all()
            
            # Convert to AI format
            ai_timetable = []
            for entry in timetable_entries:
                ai_timetable.append({
                    'day': entry.day_of_week,
                    'time_slot': entry.time_slot,
                    'course_id': entry.subject.code,
                    'teacher_id': entry.teacher.employee_id,
                    'room_id': entry.room.room_number,
                    'section_id': f"{entry.grade}{entry.section}"
                })
            
            # Load AI prompt
            prompt = self._load_repair_prompt()
            
            # Format prompt with data
            formatted_prompt = prompt.format(json_data=json.dumps(ai_timetable, indent=2))
            
            # Generate response
            response = self.model.generate_content(
                formatted_prompt,
                generation_config=self.generation_config
            )
            
            # Parse AI response
            ai_response = json.loads(response.text)
            
            # Apply repairs
            if ai_response.get('repaired_timetable'):
                version_name = f"AI_Repaired_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self._save_timetable(ai_response['repaired_timetable'], version_name)
            
            return {
                'success': True,
                'version': version_name,
                'changes': ai_response.get('explanation_of_changes', [])
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _prepare_timetable_data(self):
        """Prepare data for timetable generation"""
        # Get teachers
        teachers = Teacher.query.join(User).all()
        teachers_data = []
        for teacher in teachers:
            teachers_data.append({
                'id': teacher.employee_id,
                'name': teacher.user.get_full_name(),
                'max_hours_week': teacher.max_hours_week,
                'specialization': teacher.specialization or '',
                'is_available': teacher.is_available
            })
        
        # Get subjects
        subjects = Subject.query.join(Teacher, isouter=True).all()
        subjects_data = []
        for subject in subjects:
            subjects_data.append({
                'id': subject.code,
                'name': subject.name,
                'teacher_id': subject.teacher.employee_id if subject.teacher else None,
                'weekly_hours': subject.weekly_hours,
                'grade_level': subject.grade_level,
                'requires_lab': subject.requires_lab,
                'max_students': subject.max_students
            })
        
        # Get rooms
        rooms = Room.query.all()
        rooms_data = []
        for room in rooms:
            rooms_data.append({
                'id': room.room_number,
                'name': room.name,
                'capacity': room.capacity,
                'type': room.room_type,
                'is_available': room.is_available
            })
        
        # Get sections
        sections_data = []
        for grade in ['UKG', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']:
            for section in ['A', 'B', 'C', 'D']:
                sections_data.append({
                    'id': f"{grade}{section}",
                    'grade': grade,
                    'section': section
                })
        
        return {
            'teachers': teachers_data,
            'courses': subjects_data,
            'rooms': rooms_data,
            'sections': sections_data
        }
    
    def _prepare_exam_data(self):
        """Prepare data for exam scheduling"""
        # Get subjects that need exams
        subjects = Subject.query.filter_by(is_active=True).all()
        subjects_data = []
        for subject in subjects:
            subjects_data.append(f"{subject.name}-{subject.grade_level}")
        
        # Get students
        students = Student.query.join(User).all()
        students_data = []
        for student in students:
            students_data.append({
                'id': student.student_id,
                'name': student.user.get_full_name(),
                'section': f"{student.grade}{student.section}",
                'friends': []  # Would be populated from a friends/conflicts table
            })
        
        # Get rooms
        rooms = Room.query.all()
        rooms_data = []
        for room in rooms:
            rooms_data.append({
                'id': room.room_number,
                'capacity': room.capacity
            })
        
        return {
            'subjects_for_exam': subjects_data,
            'students': students_data,
            'rooms': rooms_data
        }
    
    def _load_timetable_prompt(self):
        """Load timetable generation prompt"""
        return """
You are a master scheduler for Indian schools. Based on the following JSON data of teachers, subjects, classrooms, and student sections, generate an optimal, conflict-free weekly timetable.

Input Data (JSON):
{json_data}

Hard Constraints (Must be met):

1. No Conflicts: A teacher, section, or room cannot be in two places at once.
2. Teacher Workload: A teacher's total weekly hours must not exceed their specified max_hours_week. Distribute classes evenly throughout the week.
3. No Gaps: Student timetables must be contiguous. No free periods are allowed between two classes on the same day.
4. Grade Timings: Classes for lower grades (UKG-5th) must be scheduled to finish by 1:30 PM. Higher grades can have classes throughout the day.
5. Lab Exclusivity: Lab sessions (reqd_lab: true) are only for higher grades (9th and above) and must be scheduled in a 'Lab' type room.
6. Full Coverage: All required weekly hours for every subject in every section must be scheduled.

Time Slots Available:
- 08:00-09:00
- 09:00-10:00
- 10:00-11:00
- 11:00-12:00
- 12:00-13:00
- 13:00-14:00
- 14:00-15:00
- 15:00-16:00

Days: Monday, Tuesday, Wednesday, Thursday, Friday

Output Format (JSON):
Return a single JSON array of timetable entry objects.
[ 
  {{ 
    "day": "Monday", 
    "time_slot": "09:00-10:00", 
    "course_id": "PHY12", 
    "teacher_id": "T004", 
    "room_id": "R101", 
    "section_id": "SEC12A" 
  }}, 
  ... 
]
"""
    
    def _load_exam_prompt(self):
        """Load exam scheduling prompt"""
        return """
You are an exam logistics coordinator. Given a list of subjects for final exams and a list of available rooms with their seating capacity, generate a conflict-free exam timetable and a detailed seating plan for each exam.

Input Data (JSON):
{json_data}

Hard Constraints:

1. No student can have two exams at the same time.
2. Spread exams out, aiming for a maximum of one exam per day for any student.
3. The number of students in a room cannot exceed its capacity.
4. Seating Arrangement: In the seating plan, ensure that no two students listed as 'friends' are seated in adjacent seats (front, back, left, or right).

Exam Dates Available: March 15-30, 2024 (Monday to Friday only)
Exam Times: 09:00-12:00, 14:00-17:00

Output Format (JSON):
{{
  "exam_schedule": [
    {{
      "date": "2024-03-15",
      "time": "09:00-12:00",
      "subject_id": "Math-10",
      "rooms_assigned": ["R201", "R202"]
    }},
    ...
  ],
  "seating_plan": [
    {{
      "exam_id": "Math-10-2024-03-15",
      "room_id": "R201",
      "map": [
        ["S001", "S015", "S023"],
        ["S002", null, "S045"],
        ...
      ]
    }},
    ...
  ]
}}
"""
    
    def _load_repair_prompt(self):
        """Load timetable repair prompt"""
        return """
You are a conflict resolution expert. The user has manually edited a timetable, potentially creating conflicts. The following JSON contains the entire modified timetable. Analyze it, identify all conflicts, and return a repaired, conflict-free version. Also, provide a human-readable explanation of the changes you made.

Input Data (JSON):
{json_data}

Task:
1. Identify all conflicts (teacher, room, section clashes).
2. Resolve the conflicts by rescheduling the minimum number of classes necessary.
3. Prioritize keeping the user's manual changes if they are conflict-free.

Output Format (JSON):
{{
  "repaired_timetable": [...],
  "explanation_of_changes": [
    "Moved Physics class for 12A from Monday at 10:00 to Wednesday at 14:00 to resolve a clash for Dr. Sharma.",
    ...
  ]
}}
"""
    
    def _save_timetable(self, ai_timetable, version_name):
        """Save AI-generated timetable to database"""
        # Clear existing entries for this version
        TimetableEntry.query.filter_by(timetable_version=version_name).delete()
        
        # Create mapping dictionaries
        subject_map = {s.code: s.id for s in Subject.query.all()}
        teacher_map = {t.employee_id: t.id for t in Teacher.query.all()}
        room_map = {r.room_number: r.id for r in Room.query.all()}
        
        # Save new entries
        for entry_data in ai_timetable:
            try:
                # Parse section_id to get grade and section
                section_id = entry_data['section_id']
                if section_id.startswith('SEC'):
                    # Handle format like "SEC12A"
                    grade_section = section_id[3:]  # Remove "SEC"
                    if len(grade_section) >= 2:
                        grade = grade_section[:-1]  # "12"
                        section = grade_section[-1]  # "A"
                    else:
                        continue
                else:
                    # Handle format like "12A"
                    if len(section_id) >= 2:
                        grade = section_id[:-1]  # "12"
                        section = section_id[-1]  # "A"
                    else:
                        continue
                
                # Create timetable entry
                entry = TimetableEntry(
                    day_of_week=entry_data['day'],
                    time_slot=entry_data['time_slot'],
                    subject_id=subject_map.get(entry_data['course_id']),
                    teacher_id=teacher_map.get(entry_data['teacher_id']),
                    room_id=room_map.get(entry_data['room_id']),
                    grade=grade,
                    section=section,
                    timetable_version=version_name,
                    is_manual_override=False
                )
                
                if entry.subject_id and entry.teacher_id and entry.room_id:
                    db.session.add(entry)
                    
            except Exception as e:
                print(f"Error saving timetable entry: {str(e)}")
                continue
        
        db.session.commit()
    
    def _save_exam_schedule(self, ai_schedule):
        """Save AI-generated exam schedule to database"""
        # Clear existing exam schedules
        ExamSchedule.query.delete()
        ExamAssignment.query.delete()
        
        # Create mapping dictionaries
        subject_map = {}
        for subject in Subject.query.all():
            key = f"{subject.name}-{subject.grade_level}"
            subject_map[key] = subject.id
        
        student_map = {s.student_id: s.id for s in Student.query.all()}
        room_map = {r.room_number: r.id for r in Room.query.all()}
        
        # Save exam schedules
        for exam_data in ai_schedule.get('exam_schedule', []):
            try:
                # Find subject
                subject_key = exam_data['subject_id']
                subject_id = subject_map.get(subject_key)
                
                if not subject_id:
                    continue
                
                subject = Subject.query.get(subject_id)
                
                # Create exam schedule
                exam = ExamSchedule(
                    subject_id=subject_id,
                    exam_date=datetime.strptime(exam_data['date'], '%Y-%m-%d').date(),
                    start_time=datetime.strptime(exam_data['time'].split('-')[0], '%H:%M').time(),
                    end_time=datetime.strptime(exam_data['time'].split('-')[1], '%H:%M').time(),
                    duration_minutes=180,  # 3 hours default
                    grade=subject.grade_level,
                    exam_type='Final'
                )
                
                db.session.add(exam)
                db.session.flush()  # Get exam ID
                
                # Save seating plan for this exam
                for seating_data in ai_schedule.get('seating_plan', []):
                    if seating_data['exam_id'] == subject_key + '-' + exam_data['date']:
                        self._save_seating_plan(exam.id, seating_data, student_map, room_map)
                
            except Exception as e:
                print(f"Error saving exam schedule: {str(e)}")
                continue
        
        db.session.commit()
    
    def _save_seating_plan(self, exam_id, seating_data, student_map, room_map):
        """Save seating plan for an exam"""
        try:
            room_id = room_map.get(seating_data['room_id'])
            if not room_id:
                return
            
            seating_map = seating_data['map']
            
            for row_idx, row in enumerate(seating_map):
                for col_idx, student_id in enumerate(row):
                    if student_id and student_id in student_map:
                        assignment = ExamAssignment(
                            exam_schedule_id=exam_id,
                            student_id=student_map[student_id],
                            room_id=room_id,
                            seat_number=f"{chr(65 + row_idx)}{col_idx + 1}",  # A1, A2, etc.
                            row=row_idx,
                            column=col_idx
                        )
                        db.session.add(assignment)
                        
        except Exception as e:
            print(f"Error saving seating plan: {str(e)}")
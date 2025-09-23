import json
import os
import requests
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, session, redirect, url_for, render_template, g, send_file
from sqlalchemy.orm import joinedload
from sqlalchemy import exc

from extensions import db
from models import Exam, ExamSeating, Student, Classroom, Subject, Course, Teacher, StudentSection
from utils import log_activity, validate_json_request

exams_bp = Blueprint('exams', __name__, url_prefix='/exams')

@exams_bp.route('/')
def manage_exams():
    """Render the exam management page."""
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    return render_template('exams.html')

@exams_bp.route('/api/exams', methods=['GET', 'POST'])
@exams_bp.route('/api/exams/<int:exam_id>', methods=['PUT', 'DELETE'])
def handle_exams(exam_id=None):
    """Handle exam CRUD operations."""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
    try:
        if request.method == 'GET':
            exams = Exam.query.options(
                joinedload(Exam.subject),
                joinedload(Exam.course)
            ).all()
            
            exams_data = []
            for exam in exams:
                exam_data = {
                    'id': exam.id,
                    'name': exam.name,
                    'date': exam.date.isoformat(),
                    'duration': exam.duration,
                    'type': exam.type,
                    'subject_name': exam.subject.name if exam.subject else exam.course.name if exam.course else 'N/A',
                    'subject_code': exam.subject.code if exam.subject else exam.course.code if exam.course else 'N/A'
                }
                exams_data.append(exam_data)
            
            return jsonify({"exams": exams_data})
        
        if request.method in ['POST', 'PUT']:
            data, error_response, status_code = validate_json_request()
            if error_response:
                return error_response, status_code
        
        if request.method == 'POST':
            # Create new exam
            exam_date = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
            
            new_exam = Exam(
                name=data['name'],
                date=exam_date,
                duration=data.get('duration', 180),  # Default 3 hours
                type=data.get('type', 'final'),
                subject_id=data.get('subject_id'),
                course_id=data.get('course_id')
            )
            
            db.session.add(new_exam)
            db.session.commit()
            
            log_activity('info', f"Exam '{data['name']}' created.")
            return jsonify({"message": "Exam created successfully!"})
        
        elif request.method == 'PUT':
            # Update existing exam
            exam = Exam.query.get_or_404(exam_id)
            exam.name = data['name']
            exam.date = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
            exam.duration = data.get('duration', exam.duration)
            exam.type = data.get('type', exam.type)
            exam.subject_id = data.get('subject_id')
            exam.course_id = data.get('course_id')
            
            db.session.commit()
            
            log_activity('info', f"Exam '{exam.name}' updated.")
            return jsonify({"message": "Exam updated successfully!"})
        
        elif request.method == 'DELETE':
            # Delete exam
            exam = Exam.query.get_or_404(exam_id)
            exam_name = exam.name
            
            # Delete associated seating plans
            ExamSeating.query.filter_by(exam_id=exam_id).delete()
            
            db.session.delete(exam)
            db.session.commit()
            
            log_activity('warning', f"Exam '{exam_name}' deleted.")
            return jsonify({"message": "Exam deleted successfully!"})
            
    except exc.IntegrityError:
        db.session.rollback()
        return jsonify({"message": "Database integrity error occurred."}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"An unexpected error occurred: {e}"}), 500

@exams_bp.route('/api/generate_schedule', methods=['POST'])
def generate_exam_schedule():
    """Generate exam schedule and seating plan using Gemini AI."""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
    try:
        data, error_response, status_code = validate_json_request()
        if error_response:
            return error_response, status_code
        
        exam_ids = data.get('exam_ids', [])
        if not exam_ids:
            return jsonify({"message": "No exams selected for scheduling."}), 400
        
        # Get exam data
        exams = Exam.query.filter(Exam.id.in_(exam_ids)).options(
            joinedload(Exam.subject),
            joinedload(Exam.course)
        ).all()
        
        if not exams:
            return jsonify({"message": "No valid exams found."}), 400
        
        # Get students data
        students = Student.query.options(
            joinedload(Student.user),
            joinedload(Student.section)
        ).all()
        
        # Get classrooms data
        classrooms = Classroom.query.all()
        
        # Generate prompt for Gemini
        prompt = generate_exam_schedule_prompt(exams, students, classrooms)
        
        # Call Gemini API
        schedule_data = call_gemini_api(prompt)
        
        if schedule_data and 'exam_schedule' in schedule_data:
            # Save exam schedule and seating plans
            for schedule_item in schedule_data['exam_schedule']:
                # Update exam with schedule
                exam = next((e for e in exams if e.name == schedule_item['subject_id']), None)
                if exam:
                    exam.date = datetime.fromisoformat(schedule_item['date'])
                    exam.duration = schedule_item.get('duration', 180)
            
            # Save seating plans
            if 'seating_plan' in schedule_data:
                for seating_item in schedule_data['seating_plan']:
                    exam = next((e for e in exams if e.name == seating_item['exam_id'].split('-')[0]), None)
                    if exam:
                        # Clear existing seating for this exam
                        ExamSeating.query.filter_by(exam_id=exam.id).delete()
                        
                        # Add new seating plan
                        for row_idx, row in enumerate(seating_item['map']):
                            for col_idx, student_id in enumerate(row):
                                if student_id:
                                    classroom = next((c for c in classrooms if c.room_id == seating_item['room_id']), None)
                                    if classroom:
                                        seating = ExamSeating(
                                            exam_id=exam.id,
                                            student_id=student_id,
                                            classroom_id=classroom.id,
                                            seat_number=f"{row_idx + 1}-{col_idx + 1}"
                                        )
                                        db.session.add(seating)
            
            db.session.commit()
            
            log_activity('info', f"Exam schedule generated for {len(exams)} exams.")
            return jsonify({
                "message": f"Exam schedule generated successfully!",
                "schedule": schedule_data.get('exam_schedule', []),
                "changes": schedule_data.get('explanation_of_changes', [])
            })
        else:
            raise ValueError("Invalid response from Gemini API")
            
    except Exception as e:
        db.session.rollback()
        log_activity('error', f'Exam schedule generation failed: {e}')
        return jsonify({"message": f"Failed to generate exam schedule: {str(e)}"}), 500

def generate_exam_schedule_prompt(exams, students, classrooms):
    """Generate prompt for Gemini API to create exam schedule."""
    
    exams_data = []
    for exam in exams:
        exam_info = {
            'id': exam.id,
            'name': exam.name,
            'duration': exam.duration,
            'type': exam.type,
            'subject': exam.subject.name if exam.subject else exam.course.name if exam.course else 'N/A',
            'subject_code': exam.subject.code if exam.subject else exam.course.code if exam.course else 'N/A'
        }
        exams_data.append(exam_info)
    
    students_data = []
    for student in students:
        student_info = {
            'id': student.id,
            'name': student.full_name,
            'section': student.section.name if student.section else 'N/A',
            'friends': []  # Could be populated from a friends table
        }
        students_data.append(student_info)
    
    classrooms_data = []
    for classroom in classrooms:
        classroom_info = {
            'id': classroom.id,
            'room_id': classroom.room_id,
            'capacity': classroom.capacity,
            'features': classroom.features or []
        }
        classrooms_data.append(classroom_info)
    
    prompt = f"""
You are an expert exam logistics coordinator for an Indian educational institution. Generate an optimal exam schedule and seating plan based on the following data:

EXAMS TO SCHEDULE ({len(exams_data)}):
{json.dumps(exams_data, indent=2)}

STUDENTS ({len(students_data)}):
{json.dumps(students_data, indent=2)}

AVAILABLE CLASSROOMS ({len(classrooms_data)}):
{json.dumps(classrooms_data, indent=2)}

REQUIREMENTS:
1. No student can have two exams at the same time
2. Spread exams out, aiming for maximum one exam per day per student
3. Classroom capacity cannot be exceeded
4. In seating plans, ensure no two students listed as 'friends' are seated adjacent (front, back, left, right)
5. Consider exam duration and type (final, midterm, quiz)
6. Optimize for minimal conflicts and maximum efficiency

OUTPUT FORMAT (JSON):
{{
    "exam_schedule": [
        {{
            "date": "2024-03-15",
            "time": "09:00-12:00",
            "subject_id": "Math-10",
            "duration": 180,
            "rooms_assigned": ["R201", "R202"]
        }}
    ],
    "seating_plan": [
        {{
            "exam_id": "Math-10-2024-03-15",
            "room_id": "R201",
            "map": [
                ["S001", "S015", "S023"],
                ["S002", null, "S045"],
                [null, "S067", "S089"]
            ]
        }}
    ],
    "explanation_of_changes": [
        "Scheduled Math exam for Class 10 on March 15th to avoid conflicts",
        "Assigned classrooms R201 and R202 based on student count"
    ]
}}

Return ONLY the JSON object, no additional text.
"""
    
    return prompt

def call_gemini_api(prompt, max_retries=3):
    """Call Gemini API to generate exam schedule with retry logic for rate limits."""
    import time
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            
            # Handle rate limit specifically
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 5  # Exponential backoff: 5s, 10s, 20s
                    log_activity('warning', f'Rate limit hit, retrying in {wait_time} seconds (attempt {attempt + 1}/{max_retries})')
                    time.sleep(wait_time)
                    continue
                else:
                    raise ValueError("Rate limit exceeded. Please wait a few minutes before trying again.")
            
            response.raise_for_status()
            result = response.json()
            
            if 'candidates' in result and len(result['candidates']) > 0:
                content = result['candidates'][0]['content']['parts'][0]['text']
                # Clean up the response to extract JSON
                content = content.strip()
                if content.startswith('```json'):
                    content = content[7:]
                if content.endswith('```'):
                    content = content[:-3]
                
                return json.loads(content)
            else:
                raise ValueError("No valid response from Gemini API")
                
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2  # Shorter wait for network errors
                log_activity('warning', f'Network error, retrying in {wait_time} seconds: {e}')
                time.sleep(wait_time)
                continue
            else:
                log_activity('error', f'Gemini API call failed after {max_retries} attempts: {e}')
                raise ValueError(f"Failed to generate exam schedule: {e}")
        except Exception as e:
            log_activity('error', f'Gemini API call failed: {e}')
            raise ValueError(f"Failed to generate exam schedule: {e}")

@exams_bp.route('/api/seating/<int:exam_id>')
def get_seating_plan(exam_id):
    """Get seating plan for a specific exam."""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
    try:
        exam = Exam.query.get_or_404(exam_id)
        seating_plans = ExamSeating.query.filter_by(exam_id=exam_id).options(
            joinedload(ExamSeating.student),
            joinedload(ExamSeating.classroom)
        ).all()
        
        # Group by classroom
        classrooms = {}
        for seating in seating_plans:
            room_id = seating.classroom.room_id
            if room_id not in classrooms:
                classrooms[room_id] = {
                    'room_id': room_id,
                    'capacity': seating.classroom.capacity,
                    'seats': {}
                }
            
            row, col = seating.seat_number.split('-')
            classrooms[room_id]['seats'][f"{row}-{col}"] = {
                'student_id': seating.student_id,
                'student_name': seating.student.full_name,
                'seat_number': seating.seat_number
            }
        
        return jsonify({
            "exam_name": exam.name,
            "exam_date": exam.date.isoformat(),
            "classrooms": classrooms
        })
        
    except Exception as e:
        return jsonify({"message": f"Error fetching seating plan: {str(e)}"}), 500

@exams_bp.route('/api/export/<int:exam_id>')
def export_exam_schedule(exam_id):
    """Export exam schedule and seating plan as PDF."""
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    # This would integrate with a PDF generation library like ReportLab
    # For now, return a placeholder response
    return jsonify({"message": "Export functionality will be implemented with PDF generation library"})

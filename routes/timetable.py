import time
import random
import json
import os
import requests
from flask import Blueprint, request, redirect, url_for, session, g, jsonify, render_template
from sqlalchemy.orm import joinedload
from models import db, Teacher, Student, StudentSection, Classroom, Subject, Course, AppConfig, TimetableEntry, SchoolGroup, Grade, Stream, Semester, Department
from utils import set_config, log_activity, validate_json_request

# Import the generator dynamically
try:
    from timetable_generator import TimetableGenerator
except ImportError:
    TimetableGenerator = None

timetable_bp = Blueprint('timetable', __name__)

@timetable_bp.route('/timetable')
def view_timetable():
    """Renders the main timetable view page."""
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    # Pass settings needed to build the timetable grid on the frontend
    working_days_raw = AppConfig.query.filter_by(key='working_days').first().value
    
    # Handle different working_days formats
    if working_days_raw.startswith('['):
        # Already JSON array
        working_days = json.loads(working_days_raw)
    else:
        # Convert string like "Monday - Friday" to array
        if 'Monday - Friday' in working_days_raw:
            working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        elif 'Monday - Saturday' in working_days_raw:
            working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        else:
            # Fallback to default
            working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    settings = {
        'start_time': AppConfig.query.filter_by(key='start_time').first().value,
        'end_time': AppConfig.query.filter_by(key='end_time').first().value,
        'period_duration': AppConfig.query.filter_by(key='period_duration').first().value,
        'working_days': working_days,
        'breaks': json.loads(AppConfig.query.filter_by(key='breaks').first().value),
    }
    return render_template('timetable.html', settings=settings)

@timetable_bp.route('/api/timetable_data')
def get_timetable_data():
    """Provides the raw timetable data as JSON for the frontend to render."""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        entries = TimetableEntry.query.options(
            joinedload(TimetableEntry.teacher),
            joinedload(TimetableEntry.subject),
            joinedload(TimetableEntry.course),
            joinedload(TimetableEntry.section).joinedload(StudentSection.department).joinedload(Department.semester),
            joinedload(TimetableEntry.classroom)
        ).all()
        
        data = []
        for entry in entries:
            item = {
                'id': entry.id,
                'day': entry.day,
                'period': entry.period,
                'teacher_id': entry.teacher_id,
                'teacher': entry.teacher.full_name if entry.teacher else "Unknown",
                'section_id': entry.section_id,
                'section': entry.section.name if entry.section else "Unknown",
                'classroom_id': entry.classroom_id,
                'classroom': entry.classroom.room_id if entry.classroom else "Unknown",
                'semester_name': entry.section.department.semester.name if entry.section and entry.section.department and entry.section.department.semester else "Unknown",
                'department_name': entry.section.department.name if entry.section and entry.section.department else "Unknown"
            }
            
            if g.app_mode == 'school' and entry.subject:
                item['subject'] = f"{entry.subject.name} ({entry.subject.code})"
                item['subject_id'] = entry.subject_id
            elif g.app_mode == 'college' and entry.course:
                item['subject'] = f"{entry.course.name} ({entry.course.code})"
                item['course_id'] = entry.course_id
            else:
                item['subject'] = "N/A"
                item['subject_id'] = None
                item['course_id'] = None
                
            data.append(item)
        
        return jsonify(data)
    except Exception as e:
        log_activity('error', f'Error fetching timetable data: {e}')
        return jsonify({"error": "Failed to fetch timetable data"}), 500

@timetable_bp.route('/api/sections')
def get_sections():
    """Get all sections for filtering."""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        sections = StudentSection.query.options(
            joinedload(StudentSection.students)
        ).all()
        
        sections_data = []
        for section in sections:
            sections_data.append({
                'id': section.id,
                'name': section.name,
                'capacity': section.capacity,
                'student_count': len(section.students)
            })
            
        return jsonify({"sections": sections_data})
    except Exception as e:
        log_activity('error', f'Error fetching sections: {e}')
        return jsonify({"error": "Failed to fetch sections"}), 500

@timetable_bp.route('/api/classrooms')
def get_classrooms():
    """Get all classrooms for filtering."""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        classrooms = Classroom.query.all()
        
        classrooms_data = []
        for classroom in classrooms:
            classrooms_data.append({
                'id': classroom.id,
                'room_id': classroom.room_id,
                'capacity': classroom.capacity,
                'features': classroom.features or []
            })
            
        return jsonify({"classrooms": classrooms_data})
    except Exception as e:
        log_activity('error', f'Error fetching classrooms: {e}')
        return jsonify({"error": "Failed to fetch classrooms"}), 500


def generate_timetable_algorithm(sections, teachers, classrooms, subjects_or_courses, settings):
    """Generate timetable using traditional algorithm instead of AI."""
    print("🧮 Using algorithm-based timetable generation...")
    
    entries = []
    working_days = settings.get('working_days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
    periods_per_day = 8  # Default 8 periods per day
    
    # Track assigned resources
    assigned_teachers = {}  # {teacher_id: {day: [periods]}}
    assigned_rooms = {}     # {room_id: {day: [periods]}}
    assigned_times = set()  # {(day, period)}
    
    # Get available subjects/courses
    available_subjects = subjects_or_courses
    
    for section in sections:
        print(f"📚 Processing section: {section.name}")
        
        # Get teachers who can teach this section's subjects/courses
        section_teachers = []
        for teacher in teachers:
            if g.app_mode == 'school':
                if hasattr(teacher, 'subjects') and teacher.subjects:
                    section_teachers.append(teacher)
            else:
                if hasattr(teacher, 'courses') and teacher.courses:
                    section_teachers.append(teacher)
        
        # Get relevant subjects/courses for this section
        if g.app_mode == 'school':
            relevant_subjects = available_subjects
        else:
            relevant_subjects = []
            for course in available_subjects:
                if hasattr(course, 'department_id') and course.department_id == section.department_id:
                    relevant_subjects.append(course)
            if not relevant_subjects:
                relevant_subjects = available_subjects
        
        # Generate timetable for this section
        section_entries = generate_section_timetable(
            section, section_teachers, classrooms, relevant_subjects, 
            working_days, periods_per_day, assigned_teachers, assigned_rooms, assigned_times
        )
        
        entries.extend(section_entries)
        print(f"✅ Generated {len(section_entries)} entries for {section.name}")
    
    return entries

def generate_section_timetable(section, teachers, classrooms, subjects, working_days, periods_per_day, assigned_teachers, assigned_rooms, assigned_times):
    """Generate timetable for a single section using greedy algorithm."""
    entries = []
    
    # Shuffle to add randomness
    import random
    random.shuffle(teachers)
    random.shuffle(classrooms)
    random.shuffle(subjects)
    
    for day in working_days:
        for period in range(1, periods_per_day + 1):
            # Skip if this time slot is already assigned
            if (day, period) in assigned_times:
                continue
            
            # Try to find a valid assignment
            for teacher in teachers:
                # Check if teacher is available at this time
                if teacher.id in assigned_teachers:
                    if day in assigned_teachers[teacher.id]:
                        if period in assigned_teachers[teacher.id][day]:
                            continue
                
                # Find a suitable subject/course for this teacher
                suitable_subject = None
                if g.app_mode == 'school':
                    # For school mode, check if teacher teaches this subject
                    for subject in subjects:
                        if hasattr(teacher, 'subjects') and subject in teacher.subjects:
                            suitable_subject = subject
                            break
                else:
                    # For college mode, check if teacher teaches this course
                    for course in subjects:
                        if hasattr(teacher, 'courses') and course in teacher.courses:
                            suitable_subject = course
                            break
                
                if not suitable_subject:
                    continue
                
                # Find an available classroom
                for classroom in classrooms:
                    # Check if classroom is available at this time
                    if classroom.id in assigned_rooms:
                        if day in assigned_rooms[classroom.id]:
                            if period in assigned_rooms[classroom.id][day]:
                                continue
                    
                    # Create timetable entry
                    entry = {
                        'day': day,
                        'period': period,
                        'teacher_id': teacher.id,
                        'section_id': section.id,
                        'classroom_id': classroom.id
                    }
                    
                    if g.app_mode == 'school':
                        entry['subject_id'] = suitable_subject.id
                        entry['course_id'] = None
                    else:
                        entry['course_id'] = suitable_subject.id
                        entry['subject_id'] = None
                    
                    entries.append(entry)
                    
                    # Update assigned resources
                    if teacher.id not in assigned_teachers:
                        assigned_teachers[teacher.id] = {}
                    if day not in assigned_teachers[teacher.id]:
                        assigned_teachers[teacher.id][day] = []
                    assigned_teachers[teacher.id][day].append(period)
                    
                    if classroom.id not in assigned_rooms:
                        assigned_rooms[classroom.id] = {}
                    if day not in assigned_rooms[classroom.id]:
                        assigned_rooms[classroom.id][day] = []
                    assigned_rooms[classroom.id][day].append(period)
                    
                    assigned_times.add((day, period))
                    
                    # Break out of classroom loop
                    break
                
                # Break out of teacher loop if we found a valid assignment
                if (day, period) in assigned_times:
                    break
    
    return entries

def generate_individual_section_prompt(teachers, section, classrooms, subjects_or_courses, settings, assigned_resources):
    """Generate a focused prompt for a single section with conflict tracking."""
    print(f"📝 Generating individual prompt for section: {section.name}")
    
    # Get teachers who can teach this section's subjects/courses
    section_teachers = []
    for teacher in teachers:
        if g.app_mode == 'school':
            # For school mode, check if teacher teaches any subjects
            if hasattr(teacher, 'subjects') and teacher.subjects:
                section_teachers.append(teacher)
        else:
            # For college mode, check if teacher teaches any courses
            if hasattr(teacher, 'courses') and teacher.courses:
                section_teachers.append(teacher)
    
    # Get relevant subjects/courses for this section
    if g.app_mode == 'school':
        relevant_subjects = subjects_or_courses
    else:
        # For college mode, get courses relevant to this section's department
        relevant_subjects = []
        for course in subjects_or_courses:
            if hasattr(course, 'department_id') and course.department_id == section.department_id:
                relevant_subjects.append(course)
        
        # If no department-specific courses found, use all courses
        if not relevant_subjects:
            relevant_subjects = subjects_or_courses
    
    # Get available classrooms
    available_classrooms = classrooms
    
    # Create focused data structures
    teachers_data = []
    for teacher in section_teachers:
        teacher_info = {
            'id': teacher.id,
            'name': teacher.full_name,
            'max_hours': teacher.max_weekly_hours,
            'courses': [c.name for c in teacher.courses] if hasattr(teacher, 'courses') else [],
            'subjects': [s.name for s in teacher.subjects] if hasattr(teacher, 'subjects') else []
        }
        teachers_data.append(teacher_info)
    
    section_data = {
        'id': section.id,
        'name': section.name,
        'capacity': section.capacity,
        'department': section.department.name if section.department else 'Unknown',
        'semester': section.department.semester.name if section.department and section.department.semester else 'Unknown'
    }
    
    classrooms_data = []
    for classroom in available_classrooms:
        classroom_info = {
            'id': classroom.id,
            'room_id': classroom.room_id,
            'capacity': classroom.capacity,
            'features': classroom.features.split(',') if classroom.features else []
        }
        classrooms_data.append(classroom_info)
    
    subjects_data = []
    for subject in relevant_subjects:
        subject_info = {
            'id': subject.id,
            'name': subject.name,
            'code': subject.code if hasattr(subject, 'code') else '',
            'credits': subject.credits if hasattr(subject, 'credits') else 0
        }
        subjects_data.append(subject_info)
    
    # Create conflict tracking context
    assigned_teachers = assigned_resources.get('teachers', {})
    assigned_rooms = assigned_resources.get('rooms', {})
    assigned_times = assigned_resources.get('times', set())
    
    # Create focused prompt with conflict tracking
    prompt = f"""You are a timetable scheduling assistant.
We are generating timetables **one section at a time**.
You must strictly follow the rules below.

Rules:
1. Generate the timetable only for Section: {section.name}.
2. Each class should have exactly one subject and teacher in each time slot.
3. Do not assign a teacher who is already scheduled in another section at that same time.
4. Do not assign a classroom that is already occupied at that same time.
5. Do not assign more than one class per time slot for this section.
6. Use the available teachers, subjects, classrooms, and time slots provided.
7. The timetable must be conflict-free across all sections.

Context (taken resources so far):
- Teachers already assigned: {assigned_teachers}
- Rooms already assigned: {assigned_rooms}
- Time slots already filled: {list(assigned_times)}

SECTION DETAILS:
{json.dumps(section_data, indent=2)}

AVAILABLE TEACHERS ({len(teachers_data)}):
{json.dumps(teachers_data, indent=2)}

AVAILABLE CLASSROOMS ({len(classrooms_data)}):
{json.dumps(classrooms_data, indent=2)}

AVAILABLE {'SUBJECTS' if g.app_mode == 'school' else 'COURSES'} ({len(subjects_data)}):
{json.dumps(subjects_data, indent=2)}

SCHEDULE SETTINGS:
- Working Days: {', '.join(settings.get('working_days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']))}
- Start Time: {settings.get('start_time', '09:00')}
- End Time: {settings.get('end_time', '17:00')}
- Period Duration: {settings.get('period_duration', 50)} minutes

REQUIREMENTS:
1. Generate 5-8 periods per day for each working day
2. Each teacher can only teach subjects/courses they are assigned to
3. No teacher can teach multiple sections at the same time
4. Each classroom can only be used by one section at a time
5. Use ONLY the exact IDs provided above - do not invent or modify any IDs
6. Avoid conflicts with already assigned resources
7. CRITICAL: Only use course_id values that exist in the courses list above

OUTPUT: JSON array with day, period, teacher_id, section_id, classroom_id, {'subject_id' if g.app_mode == 'school' else 'course_id'}

VALID COURSE IDs TO USE: {[c.id for c in subjects_or_courses] if g.app_mode == 'college' else 'N/A'}

Generate complete timetable for {section.name}:"""
    
    return prompt

def generate_gemini_prompt(teachers, sections, classrooms, subjects_or_courses, settings):
    """Generate sophisticated prompt for Gemini API to create realistic timetable."""
    
    # Enhanced teacher data with expertise and preferences
    teachers_data = []
    for teacher in teachers:
        teacher_info = {
            'id': teacher.id,
            'name': teacher.full_name,
            'max_hours_week': teacher.max_weekly_hours,
            'subjects': [s.id for s in teacher.subjects] if teacher.subjects else [],
            'courses': [c.id for c in teacher.courses] if teacher.courses else [],
            'expertise_level': 'senior' if teacher.max_weekly_hours > 25 else 'junior',
            'preferred_periods': [1, 2, 3] if teacher.max_weekly_hours > 25 else [4, 5, 6],  # Senior teachers prefer morning
            'homeroom_eligible': teacher.max_weekly_hours > 20  # Can be homeroom teacher
        }
        teachers_data.append(teacher_info)
    
    # Enhanced section data with age-appropriate constraints
    sections_data = []
    for section in sections:
        # Ensure grade_level is a string
        if section.grade:
            grade_level = str(section.grade.name) if hasattr(section.grade, 'name') else 'Unknown'
        else:
            grade_level = 'Unknown'
        
        # Ensure grade_level is a string before calling .lower()
        grade_level_str = str(grade_level).lower()
        is_primary = any(grade in grade_level_str for grade in ['1', '2', '3', '4', '5', 'ukg', 'lkg'])
        
        section_info = {
            'id': section.id,
            'name': section.name,
            'capacity': section.capacity,
            'student_count': len(section.students),
            'grade_level': grade_level,
            'stream': None,  # StudentSection doesn't have direct stream relationship
            'age_group': 'primary' if is_primary else 'secondary',
            'max_periods_per_day': 6 if is_primary else 8,
            'preferred_end_time': '13:30' if is_primary else '16:00',
            'needs_homeroom_teacher': is_primary,
            'department_id': section.department_id,
            'department_name': section.department.name if section.department else None,
            'semester_id': section.department.semester_id if section.department else None,
            'semester_name': section.department.semester.name if section.department and section.department.semester else None
        }
        sections_data.append(section_info)
    
    # Enhanced classroom data with specialized features
    classrooms_data = []
    for classroom in classrooms:
        # Process features properly - it's a string, not a list
        features_str = str(classroom.features or '')
        features_list = [f.strip() for f in features_str.split(',') if f.strip()] if features_str else []
        
        classroom_info = {
            'id': classroom.id,
            'room_id': classroom.room_id,
            'capacity': classroom.capacity,
            'features': features_list,
            'type': 'lab' if 'lab' in features_str.lower() else 'regular',
            'floor': classroom.room_id[-1] if classroom.room_id and classroom.room_id[-1].isdigit() else '1'
        }
        classrooms_data.append(classroom_info)
    
    # Enhanced subject data with complexity and prerequisites
    subjects_data = []
    for subject in subjects_or_courses:
        if g.app_mode == 'school':
            subject_info = {
                'id': subject.id,
                'name': subject.name,
                'code': subject.code,
                'weekly_hours': subject.weekly_hours,
                'is_elective': subject.is_elective,
                'stream': str(subject.stream.name) if subject.stream and hasattr(subject.stream, 'name') else None,
                'complexity': 'high' if 'math' in str(subject.name).lower() or 'physics' in str(subject.name).lower() else 'medium',
                'best_periods': [1, 2] if 'math' in str(subject.name).lower() else [3, 4, 5],
                'consecutive_periods': True if subject.weekly_hours > 4 else False,
                'requires_lab': subject.requires_lab if hasattr(subject, 'requires_lab') else False
            }
        else:
            subject_info = {
                'id': subject.id,
                'name': subject.name,
                'code': subject.code,
                'credits': subject.credits,
                'course_type': subject.course_type,
                'department': str(subject.department.name) if subject.department and hasattr(subject.department, 'name') else None,
                'complexity': 'high' if 'math' in str(subject.name).lower() or 'physics' in str(subject.name).lower() else 'medium',
                'best_periods': [1, 2] if 'math' in str(subject.name).lower() else [3, 4, 5],
                'consecutive_periods': True if subject.credits > 3 else False
            }
        subjects_data.append(subject_info)
    
    prompt = f"""
You are "Helios," an expert AI scheduler for Indian educational institutions with deep understanding of pedagogical best practices and real-world constraints. Generate an optimal weekly timetable that mirrors how a top-tier school/college would actually operate.

INSTITUTION TYPE: {g.app_mode.upper()}
WORKING DAYS: {', '.join(settings.get('working_days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']))}
SCHOOL TIMINGS: {settings.get('start_time', '08:00')} - {settings.get('end_time', '16:00')}
PERIOD DURATION: {settings.get('period_duration', 45)} minutes

TEACHERS ({len(teachers_data)}):
{json.dumps(teachers_data, indent=2)}

IMPORTANT: The teacher IDs above are the ONLY valid teacher IDs. Use these exact IDs in your timetable entries.

STUDENT SECTIONS ({len(sections_data)}):
{json.dumps(sections_data, indent=2)}

IMPORTANT: The section IDs above are the ONLY valid section IDs. Use these exact IDs in your timetable entries.

CLASSROOMS ({len(classrooms_data)}):
{json.dumps(classrooms_data, indent=2)}

IMPORTANT: The classroom IDs above are the ONLY valid classroom IDs. Use these exact IDs in your timetable entries.

SUBJECTS/COURSES ({len(subjects_data)}):
{json.dumps(subjects_data, indent=2)}

IMPORTANT: The subject/course IDs above are the ONLY valid subject/course IDs. Use these exact IDs in your timetable entries.

CRITICAL REAL-WORLD CONSTRAINTS:

1. TEACHER-SUBJECT ASSIGNMENT (ABSOLUTELY CRITICAL):
   - Teachers can ONLY teach subjects/courses they are explicitly assigned to
   - Check each teacher's 'assigned_courses' and 'assigned_subjects' arrays
   - If a teacher is not assigned to a subject/course, they CANNOT teach it under any circumstances
   - Example: If Teacher A is only assigned to "DS" course, they can ONLY teach DS to sections that have DS
   - Do not assign teachers to subjects they are not qualified/assigned to teach

2. SEMESTER-DEPARTMENT-SUBJECT MAPPING (CRITICAL):
   - Each section belongs to a specific semester and department
   - Only assign subjects/courses that are relevant to that semester-department combination
   - Example: If "DS" course exists only for "SEM 1 Electronics" students, only assign DS to those sections
   - Do not assign irrelevant subjects to sections

3. SECTION-SPECIFIC TIMETABLES (CRITICAL):
   - Generate SEPARATE timetables for EACH section - no sharing of periods between sections
   - Each section must have its own complete weekly schedule
   - Sections can have different subjects/courses based on their department/semester
   - NO conflicts between sections - each section operates independently

4. ROOM CONFLICT AVOIDANCE (CRITICAL):
   - Each classroom can only be used by ONE section at a time
   - Check classroom capacity matches section size
   - Distribute classroom usage evenly across all sections
   - Ensure no double-booking of classrooms

5. SEMESTER-DEPARTMENT-SECTION HIERARCHY:
   - Organize timetable by semester → department → section structure
   - Each section belongs to a specific department
   - Each department belongs to a specific semester
   - Create separate timetables for each section within its department

3. TEACHER CONSISTENCY & RELATIONSHIPS:
   - Same teacher should teach the same subject to the same section throughout the week
   - Maintain teacher-student relationships for better learning outcomes
   - Senior teachers (high max_hours) should handle core subjects in morning periods
   - Junior teachers can handle afternoon periods and electives

4. AGE-APPROPRIATE SCHEDULING:
   - Primary students (UKG-5th): Maximum 6 periods/day, finish by 1:30 PM
   - Secondary students: Can have 8 periods/day, finish by 4:00 PM
   - Primary students need homeroom teachers for pastoral care
   - Younger students need more breaks and varied activities

3. COGNITIVE LOAD OPTIMIZATION:
   - Math and Science subjects in morning periods (1-3) when students are fresh
   - Languages and Arts in afternoon periods (4-6)
   - Avoid consecutive heavy subjects (Math followed by Physics)
   - Include buffer periods for transitions

4. CLASSROOM & RESOURCE MANAGEMENT:
   - Lab subjects only in lab classrooms
   - Consider classroom capacity vs section size
   - Minimize student movement between floors
   - Group related subjects in nearby classrooms

5. TEACHER WORKLOAD BALANCE:
   - Distribute periods evenly across the week
   - Avoid more than 4 consecutive periods for any teacher
   - Ensure teachers have adequate preparation time
   - Consider teacher preferences for morning/afternoon periods

6. SUBJECT-SPECIFIC REQUIREMENTS:
   - Math/Science: Consecutive periods when weekly hours > 4
   - Languages: Regular intervals throughout the week
   - Physical Education: Avoid extreme weather periods
   - Lab subjects: Only for secondary students (9th+)

7. HOMEROOM TEACHER SYSTEM (Primary Students):
   - Assign dedicated homeroom teachers to primary sections
   - Homeroom teachers handle multiple subjects for their section
   - Maintain consistency in teacher-student relationships

8. EXAMINATION & ASSESSMENT CONSIDERATIONS:
   - Leave buffer periods before major exams
   - Avoid scheduling difficult subjects on exam days
   - Ensure adequate revision time

OUTPUT FORMAT:
Return a JSON array of timetable entries. Each entry must have:
- day: string (Monday, Tuesday, etc.)
- period: integer (1, 2, 3, etc.)
- teacher_id: integer (MUST use exact teacher IDs from the teachers data above)
- section_id: integer (MUST use exact section IDs from the sections data above)
- classroom_id: integer (MUST use exact classroom IDs from the classrooms data above)
- subject_id: integer (for school mode - MUST use exact subject IDs from subjects data)
- course_id: integer (for college mode - MUST use exact course IDs from courses data)

CRITICAL: Use ONLY the exact IDs provided in the data above. Do not invent or modify IDs.

EXPECTED OUTPUT SIZE: You should generate approximately {len(sections_data) * 5 * 5} entries (50 sections × 5 days × 5 periods per day = ~1250 entries). If you generate fewer entries, the timetable will be incomplete.

BREAK PERIODS:
- Break periods are automatically handled by the system
- Do NOT include break periods in your JSON output
- Only include actual class periods (1, 2, 3, etc.)
- The system will automatically insert break periods between regular periods

TIMETABLE GENERATION REQUIREMENTS:
- Generate timetables for ALL {len(sections_data)} sections (one timetable per section)
- CRITICAL: You must generate at least 5-8 periods per section for each day
- CRITICAL: Generate entries for ALL {len(sections_data)} sections, not just 2-3 sections
- Each section must have a complete weekly schedule
- NO section conflicts - each section operates independently
- NO room conflicts - each classroom can only be used by one section at a time
- Distribute teachers and classrooms evenly across all sections
- Ensure each section gets appropriate subjects/courses for their department/semester

IMPORTANT: This timetable will be used for the ENTIRE ACADEMIC YEAR. Ensure:
- Teacher assignments are consistent and sustainable
- Student learning patterns are optimized
- Teacher workload is balanced and realistic
- Classroom utilization is efficient across all sections
- The schedule reflects real-world educational best practices
- All {len(sections_data)} sections have complete, conflict-free timetables

Return ONLY the JSON array, no additional text or explanations.
"""

    return prompt

def call_gemini_api(prompt, max_retries=3):
    """Call Gemini API to generate timetable with retry logic for rate limits."""
    import time
    
    print("🚀 Starting Gemini API call...")
    log_activity('info', 'Starting Gemini API call')
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ No API key found")
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    
    print(f"✅ API key found: {api_key[:10]}...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    print(f"📡 API URL: {url}")
    
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
        
    # Check payload size before making request
    payload_size = len(json.dumps(data))
    print(f"📦 Payload size: {payload_size} characters")
    log_activity('info', f'Gemini API payload size: {payload_size} characters')
    
    if payload_size > 1000000:  # 1MB limit
        print(f"❌ Payload too large: {payload_size} chars")
        raise ValueError(f"Payload too large ({payload_size} chars). Please reduce data size.")
    
    for attempt in range(max_retries):
        try:
            print(f"🔄 Attempt {attempt + 1}/{max_retries}")
            print("📤 Sending request to Gemini API...")
            
            start_time = time.time()
            response = requests.post(url, headers=headers, json=data, timeout=120)  # Increased timeout
            request_time = time.time() - start_time
            
            print(f"📥 Response received in {request_time:.2f}s")
            print(f"📊 Status: {response.status_code} - {response.reason}")
            
            # Log detailed response info for debugging
            log_activity('info', f'Gemini API response: {response.status_code} - {response.reason} (took {request_time:.2f}s)')
            
            # Handle different error types specifically
            if response.status_code == 429:
                print("⚠️ Rate limit hit")
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 5  # Exponential backoff: 5s, 10s, 20s
                    print(f"⏳ Waiting {wait_time} seconds before retry...")
                    log_activity('warning', f'Rate limit hit, retrying in {wait_time} seconds (attempt {attempt + 1}/{max_retries})')
                    time.sleep(wait_time)
                    continue
                else:
                    print("❌ Rate limit exceeded after all retries")
                    raise ValueError("Rate limit exceeded. Please wait a few minutes before trying again.")
            
            elif response.status_code == 400:
                # Bad request - likely payload or API key issue
                error_detail = response.text
                print(f"❌ Bad request: {error_detail}")
                log_activity('error', f'Bad request (400): {error_detail}')
                if 'API key' in error_detail or 'authentication' in error_detail.lower():
                    raise ValueError("Invalid API key. Please check your GEMINI_API_KEY in .env file.")
                elif 'payload' in error_detail.lower() or 'size' in error_detail.lower():
                    raise ValueError(f"Payload too large or malformed ({payload_size} chars). Please reduce data size.")
                else:
                    raise ValueError(f"Bad request: {error_detail}")
            
            elif response.status_code == 403:
                # Forbidden - likely API key or quota issue
                error_detail = response.text
                print(f"❌ Forbidden: {error_detail}")
                log_activity('error', f'Forbidden (403): {error_detail}')
                if 'quota' in error_detail.lower():
                    raise ValueError("API quota exceeded. Please check your Gemini API usage limits.")
                elif 'billing' in error_detail.lower():
                    raise ValueError("Billing issue. Please check your Google Cloud billing.")
                else:
                    raise ValueError(f"Access forbidden: {error_detail}")
            
            elif response.status_code == 404:
                # Not found - model or endpoint issue
                print("❌ Model not found")
                raise ValueError("Model not found. Please check if 'gemini-1.5-flash' is available in your region.")
            
            elif response.status_code >= 500:
                # Server error
                print(f"❌ Server error: {response.text}")
                log_activity('error', f'Server error ({response.status_code}): {response.text}')
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 3  # Shorter wait for server errors
                    print(f"⏳ Server error, retrying in {wait_time} seconds...")
                    log_activity('warning', f'Server error, retrying in {wait_time} seconds: {response.text}')
                    time.sleep(wait_time)
                    continue
                else:
                    raise ValueError(f"Server error ({response.status_code}): {response.text}")
            
            print("✅ Response successful, parsing...")
            response.raise_for_status()
            result = response.json()
            
            print(f"📄 Response keys: {list(result.keys())}")
            
            if 'candidates' in result and len(result['candidates']) > 0:
                print("✅ Found candidates in response")
                content = result['candidates'][0]['content']['parts'][0]['text']
                print(f"📝 Content length: {len(content)} characters")
                print(f"📝 First 200 chars: {content[:200]}")
                
                # Clean up the response to extract JSON
                content = content.strip()
                if content.startswith('```json'):
                    content = content[7:]
                if content.endswith('```'):
                    content = content[:-3]
                
                print("🔄 Parsing JSON response...")
                
                # Check if response is HTML (error page)
                if content.strip().startswith('<!doctype') or content.strip().startswith('<html'):
                    print("❌ Received HTML response instead of JSON - likely API error")
                    raise ValueError("API returned HTML error page instead of JSON response")
                
                try:
                    parsed_result = json.loads(content)
                    print(f"✅ Successfully parsed JSON with {len(parsed_result)} entries")
                    log_activity('info', f'Successfully received and parsed Gemini response with {len(parsed_result)} entries')
                    return parsed_result
                except json.JSONDecodeError as e:
                    print(f"❌ JSON parsing failed: {e}")
                    print(f"📝 Content length: {len(content)} characters")
                    print(f"📝 First 500 chars: {content[:500]}")
                    print(f"📝 Last 500 chars: {content[-500:]}")
                
                # Try to fix truncated JSON
                fixed_content = content.strip()
                
                # Find the last complete JSON object
                if fixed_content.startswith('['):
                    # Find the last complete entry
                    last_complete = fixed_content.rfind('}')
                    if last_complete > 0:
                        # Find the start of the last entry
                        last_entry_start = fixed_content.rfind('{', 0, last_complete)
                        if last_entry_start > 0:
                            # Check if the last entry is complete
                            last_entry = fixed_content[last_entry_start:last_complete + 1]
                            if last_entry.count('{') == last_entry.count('}'):
                                # Last entry is complete, truncate there
                                fixed_content = fixed_content[:last_complete + 1] + ']'
                            else:
                                # Last entry is incomplete, remove it
                                fixed_content = fixed_content[:last_entry_start] + ']'
                        else:
                            fixed_content = '[]'
                    else:
                        fixed_content = '[]'
                
                # Remove trailing commas
                if fixed_content.endswith(','):
                    fixed_content = fixed_content[:-1]
                
                # Ensure proper closing
                if not fixed_content.endswith(']'):
                    fixed_content = fixed_content + ']'
                
                try:
                    parsed_result = json.loads(fixed_content)
                    print(f"✅ Successfully parsed fixed JSON with {len(parsed_result)} entries")
                    log_activity('info', f'Successfully parsed fixed JSON response with {len(parsed_result)} entries')
                    return parsed_result
                except json.JSONDecodeError as e2:
                    print(f"❌ Fixed JSON still failed: {e2}")
                    # Last resort: try to extract individual entries using regex
                    try:
                        import re
                        entries = []
                        
                        # Find all complete JSON objects using regex
                        pattern = r'\{[^{}]*"day"[^{}]*"period"[^{}]*"teacher_id"[^{}]*"section_id"[^{}]*"classroom_id"[^{}]*"course_id"[^{}]*\}'
                        matches = re.findall(pattern, content)
                        
                        for match in matches:
                            try:
                                entry = json.loads(match)
                                entries.append(entry)
                            except:
                                continue
                        
                        if entries:
                            print(f"✅ Successfully extracted {len(entries)} entries from truncated response using regex")
                            return entries
                        else:
                            # Try simpler approach - split by lines and parse each
                            lines = content.split('\n')
                            for line in lines:
                                line = line.strip()
                                if line.startswith('{') and line.endswith('},'):
                                    line = line[:-1]  # Remove trailing comma
                                elif line.startswith('{') and not line.endswith('}'):
                                    continue  # Skip incomplete lines
                                
                                try:
                                    entry = json.loads(line)
                                    entries.append(entry)
                                except:
                                    continue
                            
                            if entries:
                                print(f"✅ Successfully extracted {len(entries)} entries from truncated response using line parsing")
                                return entries
                            else:
                                raise ValueError(f"Could not extract any valid entries from truncated response")
                    except Exception as e3:
                        print(f"❌ Entry extraction failed: {e3}")
                        raise ValueError(f"Invalid JSON response from Gemini API (truncated): {e}")
            elif 'error' in result:
                print(f"❌ API Error: {result['error']}")
                raise ValueError(f"Gemini API Error: {result['error']}")
            else:
                print("❌ No valid candidates in response")
                print(f"📄 Full response: {result}")
                raise ValueError("No valid response from Gemini API")
                
        except requests.exceptions.Timeout as e:
            print(f"⏰ Request timeout: {e}")
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 5
                print(f"⏳ Timeout, retrying in {wait_time} seconds...")
                log_activity('warning', f'Request timeout, retrying in {wait_time} seconds: {e}')
                time.sleep(wait_time)
                continue
            else:
                log_activity('error', f'Request timeout after {max_retries} attempts: {e}')
                raise ValueError(f"Request timeout: {e}")
                
        except requests.exceptions.RequestException as e:
            print(f"🌐 Network error: {e}")
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2  # Shorter wait for network errors
                print(f"⏳ Network error, retrying in {wait_time} seconds...")
                log_activity('warning', f'Network error, retrying in {wait_time} seconds: {e}')
                time.sleep(wait_time)
                continue
            else:
                log_activity('error', f'Gemini API call failed after {max_retries} attempts: {e}')
                raise ValueError(f"Failed to generate timetable: {e}")
        except json.JSONDecodeError as e:
            print(f"📄 JSON decode error: {e}")
            print(f"📝 Raw content: {content[:500]}...")
            log_activity('error', f'JSON decode error: {e}')
            raise ValueError(f"Invalid JSON response from Gemini API: {e}")
        except Exception as e:
            print(f"💥 Unexpected error: {e}")
            log_activity('error', f'Gemini API call failed: {e}')
            raise ValueError(f"Failed to generate timetable: {e}")
    
    print("❌ All retry attempts failed")
    raise ValueError("All retry attempts failed")

@timetable_bp.route('/test_gemini_api', methods=['GET'])
def test_gemini_api():
    """Test Gemini API connection with a simple request."""
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    try:
        # Simple test prompt
        test_prompt = "Generate a simple JSON response: {\"status\": \"working\", \"message\": \"API connection successful\"}"
        
        result = call_gemini_api(test_prompt, max_retries=1)
        
        return jsonify({
            "success": True,
            "message": "Gemini API connection successful",
            "response": result
        })
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Gemini API connection failed"
        }), 500

@timetable_bp.route('/generate_timetable', methods=['POST'])
def generate_timetable():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    print("🚀 Starting timetable generation...")
    log_activity('info', 'Starting timetable generation')
    start_time = time.time()
    
    try:
        print("📊 Gathering data from database...")
        # Data gathering
        teachers = Teacher.query.options(joinedload(Teacher.subjects), joinedload(Teacher.courses)).all()
        print(f"👥 Found {len(teachers)} teachers")
        
        sections = StudentSection.query.options(joinedload(StudentSection.students)).all()
        print(f"🏫 Found {len(sections)} sections")
        
        classrooms = Classroom.query.all()
        print(f"🏢 Found {len(classrooms)} classrooms")
        
        subjects_or_courses = Subject.query.all() if g.app_mode == 'school' else Course.query.all()
        print(f"📚 Found {len(subjects_or_courses)} {'subjects' if g.app_mode == 'school' else 'courses'}")
        
        # Check if we have minimum required data
        if not teachers:
            print("❌ No teachers found")
            return jsonify({"message": "No teachers found. Please add teachers first."}), 400
        if not sections:
            print("❌ No sections found")
            return jsonify({"message": "No sections found. Please add sections first."}), 400
        if not classrooms:
            print("❌ No classrooms found")
            return jsonify({"message": "No classrooms found. Please add classrooms first."}), 400
        if not subjects_or_courses:
            print(f"❌ No {'subjects' if g.app_mode == 'school' else 'courses'} found")
            return jsonify({"message": f"No {'subjects' if g.app_mode == 'school' else 'courses'} found. Please add {'subjects' if g.app_mode == 'school' else 'courses'} first."}), 400
        
        print("⚙️ Loading settings...")
        settings = {item.key: item.value for item in AppConfig.query.all()}
        settings['breaks'] = json.loads(settings.get('breaks', '[]'))
        # Parse working days from string to list
        working_days_raw = settings.get('working_days', 'Monday - Friday')
        if working_days_raw.startswith('['):
            try:
                working_days = json.loads(working_days_raw)
            except json.JSONDecodeError:
                working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        else:
            if 'Monday - Friday' in working_days_raw:
                working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
            elif 'Monday - Saturday' in working_days_raw:
                working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            else:
                working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        settings['working_days'] = working_days
        print(f"📋 Settings loaded: {len(settings)} items")
        
        # Filter sections that have students
        sections_with_students = []
        for section in sections:
            student_count = len(section.students) if hasattr(section, 'students') else 0
            if student_count > 0:
                sections_with_students.append(section)
                print(f"📚 Section {section.name} has {student_count} students")
        
        print(f"🎯 Found {len(sections_with_students)} sections with students")
        
        if not sections_with_students:
            return jsonify({"message": "No sections with students found"}), 400
        
        # Clear existing timetable entries
        TimetableEntry.query.delete()
        db.session.commit()
        
        total_saved = 0
        
        # Track assigned resources to prevent conflicts
        assigned_resources = {
            'teachers': {},  # {teacher_id: {day: [periods]}}
            'rooms': {},     # {room_id: {day: [periods]}}
            'times': set()   # {(day, period)}
        }
        
        # Generate timetable using advanced hybrid algorithm
        print(f"🚀 Generating timetables for {len(sections_with_students)} sections using hybrid algorithm...")
        
        # Import the advanced generator
        from advanced_timetable_generator import TimetableGenerator
        
        # Create advanced generator
        generator = TimetableGenerator(sections_with_students, teachers, classrooms, subjects_or_courses, settings, g.app_mode)
        
        # Generate timetable using hybrid approach
        algorithm_entries = generator.generate()
        print(f"✅ Hybrid algorithm generated {len(algorithm_entries)} entries")
        
        # Process algorithm-generated entries
        for entry_data in algorithm_entries:
            # Validate required fields
            required_fields = ['day', 'period', 'teacher_id', 'section_id', 'classroom_id']
            if not all(field in entry_data for field in required_fields):
                continue
            
            # Set subject/course ID based on mode
            if g.app_mode == 'school':
                entry_data['course_id'] = None
                if 'subject_id' not in entry_data:
                    continue
            else:
                entry_data['subject_id'] = None
                if 'course_id' not in entry_data:
                    continue
            
            # Check for conflicts before adding
            day = entry_data['day']
            period = entry_data['period']
            teacher_id = entry_data['teacher_id']
            classroom_id = entry_data['classroom_id']
            
            # Check teacher conflict
            if teacher_id in assigned_resources['teachers']:
                if day in assigned_resources['teachers'][teacher_id]:
                    if period in assigned_resources['teachers'][teacher_id][day]:
                        print(f"⚠️ Teacher {teacher_id} already assigned to {day} period {period}, skipping")
                        continue
            else:
                assigned_resources['teachers'][teacher_id] = {}
            
            # Check classroom conflict
            if classroom_id in assigned_resources['rooms']:
                if day in assigned_resources['rooms'][classroom_id]:
                    if period in assigned_resources['rooms'][classroom_id][day]:
                        print(f"⚠️ Classroom {classroom_id} already assigned to {day} period {period}, skipping")
                        continue
            else:
                assigned_resources['rooms'][classroom_id] = {}
            
            # Check time slot conflict
            time_key = (day, period)
            if time_key in assigned_resources['times']:
                print(f"⚠️ Time slot {day} period {period} already assigned, skipping")
                continue
            
            # Validate IDs exist in database
            if not Teacher.query.get(teacher_id):
                print(f"⚠️ Teacher {teacher_id} not found, skipping")
                continue
            if not Classroom.query.get(classroom_id):
                print(f"⚠️ Classroom {classroom_id} not found, skipping")
                continue
            if not StudentSection.query.get(entry_data['section_id']):
                print(f"⚠️ Section {entry_data['section_id']} not found, skipping")
                continue
            
            # Validate course_id exists (for college mode)
            if g.app_mode == 'college' and 'course_id' in entry_data and entry_data['course_id']:
                if not Course.query.get(entry_data['course_id']):
                    print(f"⚠️ Course {entry_data['course_id']} not found, skipping")
                    continue
            
            # Validate subject_id exists (for school mode)
            if g.app_mode == 'school' and 'subject_id' in entry_data and entry_data['subject_id']:
                if not Subject.query.get(entry_data['subject_id']):
                    print(f"⚠️ Subject {entry_data['subject_id']} not found, skipping")
                    continue
            
            # Add to conflict tracking
            if day not in assigned_resources['teachers'][teacher_id]:
                assigned_resources['teachers'][teacher_id][day] = []
            assigned_resources['teachers'][teacher_id][day].append(period)
            
            if day not in assigned_resources['rooms'][classroom_id]:
                assigned_resources['rooms'][classroom_id][day] = []
            assigned_resources['rooms'][classroom_id][day].append(period)
            
            assigned_resources['times'].add(time_key)
            
            # Filter out invalid fields
            valid_fields = ['day', 'period', 'teacher_id', 'subject_id', 'course_id', 'section_id', 'classroom_id']
            filtered_data = {k: v for k, v in entry_data.items() if k in valid_fields}
            
            # Validate day field length
            if len(filtered_data['day']) > 10:
                filtered_data['day'] = filtered_data['day'][:10]
            
            # Validate period field
            try:
                filtered_data['period'] = int(filtered_data['period'])
            except (ValueError, TypeError):
                print(f"⚠️ Invalid period {filtered_data['period']}, skipping")
                continue
            
            # Create timetable entry
            db.session.add(TimetableEntry(**filtered_data))
            total_saved += 1
        
        print(f"✅ Processed {len(algorithm_entries)} entries from algorithm")
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"🎉 Successfully generated timetable with {total_saved} entries")
            log_activity('info', f'Successfully generated timetable with {total_saved} entries')
            
            return jsonify({
                "message": f"Timetable generated successfully with {total_saved} entries",
                "entries_count": total_saved,
                "sections_processed": len(sections_with_students)
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error saving timetable: {e}")
            log_activity('error', f'Error saving timetable: {e}')
            return jsonify({"error": f"Failed to save timetable: {e}"}), 500
            
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"💥 Full error traceback:\n{error_traceback}")
        db.session.rollback()
        log_activity('error', f'Timetable generation failed: {e}')
        log_activity('error', f'Error traceback: {error_traceback}')
        return jsonify({"message": f"Failed to generate timetable: {str(e)}"}), 500

@timetable_bp.route('/api/manage_absence', methods=['POST'])
def manage_teacher_absence():
    """AI-powered teacher absence management and substitution."""
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    data, error_response, status_code = validate_json_request()
    if error_response:
        return error_response, status_code
    
    try:
        absent_teacher_id = data.get('teacher_id')
        date = data.get('date')
        reason = data.get('reason', 'Personal leave')
        
        if not absent_teacher_id or not date:
            return jsonify({"message": "Teacher ID and date are required"}), 400
        
        # Get affected timetable entries
        affected_entries = TimetableEntry.query.filter_by(teacher_id=absent_teacher_id).all()
        
        if not affected_entries:
            return jsonify({"message": "No classes found for this teacher"}), 404
        
        # Get available substitute teachers
        available_teachers = Teacher.query.filter(Teacher.id != absent_teacher_id).all()
        
        # Generate AI prompt for substitution
        substitution_prompt = generate_substitution_prompt(affected_entries, available_teachers, reason)
        
        # Call Gemini API for substitution recommendations
        substitution_data = call_gemini_api(substitution_prompt)
        
        # Apply substitutions
        substitutions_made = []
        for substitution in substitution_data:
            entry_id = substitution['entry_id']
            substitute_teacher_id = substitution['substitute_teacher_id']
            
            entry = TimetableEntry.query.get(entry_id)
            if entry:
                original_teacher = Teacher.query.get(entry.teacher_id)
                substitute_teacher = Teacher.query.get(substitute_teacher_id)
                
                # Create substitution record
                substitution_record = {
                    'date': date,
                    'original_teacher': original_teacher.full_name,
                    'substitute_teacher': substitute_teacher.full_name,
                    'subject': str(entry.subject.name) if entry.subject else str(entry.course.name),
                    'section': entry.section.name,
                    'period': entry.period,
                    'reason': reason
                }
                substitutions_made.append(substitution_record)
                
                # Update the timetable entry
                entry.teacher_id = substitute_teacher_id
                db.session.commit()
        
        log_activity('info', f'Teacher absence managed: {len(substitutions_made)} substitutions made')
        
        return jsonify({
            "message": f"Successfully managed absence with {len(substitutions_made)} substitutions",
            "substitutions": substitutions_made
        })
        
    except Exception as e:
        db.session.rollback()
        log_activity('error', f'Teacher absence management failed: {e}')
        return jsonify({"message": f"Failed to manage absence: {str(e)}"}), 500

def generate_substitution_prompt(affected_entries, available_teachers, reason):
    """Generate prompt for AI-powered teacher substitution."""
    
    entries_data = []
    for entry in affected_entries:
        entry_info = {
            'id': entry.id,
            'day': entry.day,
            'period': entry.period,
            'subject': str(entry.subject.name) if entry.subject else str(entry.course.name),
            'section': entry.section.name,
            'grade_level': str(entry.section.grade.name) if entry.section.grade and hasattr(entry.section.grade, 'name') else 'Unknown'
        }
        entries_data.append(entry_info)
    
    teachers_data = []
    for teacher in available_teachers:
        teacher_info = {
            'id': teacher.id,
            'name': teacher.full_name,
            'subjects': [str(s.name) for s in teacher.subjects] if teacher.subjects else [],
            'courses': [str(c.name) for c in teacher.courses] if teacher.courses else [],
            'max_hours_week': teacher.max_weekly_hours,
            'current_load': len(TimetableEntry.query.filter_by(teacher_id=teacher.id).all())
        }
        teachers_data.append(teacher_info)
    
    prompt = f"""
You are "Helios," an expert AI scheduler managing teacher absence and substitution for an Indian educational institution.

ABSENCE DETAILS:
- Reason: {reason}
- Affected Classes: {len(affected_entries)}

AFFECTED CLASSES:
{json.dumps(entries_data, indent=2)}

AVAILABLE SUBSTITUTE TEACHERS:
{json.dumps(teachers_data, indent=2)}

SUBSTITUTION REQUIREMENTS:

1. EXPERTISE MATCHING:
   - Substitute teacher must be qualified to teach the subject
   - Prefer teachers with same subject expertise
   - Consider subject complexity and grade level

2. WORKLOAD BALANCE:
   - Avoid overloading any single teacher
   - Distribute substitutions across multiple teachers when possible
   - Respect teacher maximum weekly hours

3. MINIMAL DISRUPTION:
   - Maintain continuity in student learning
   - Prefer teachers familiar with the grade level
   - Consider teacher-student relationships

4. EMERGENCY PROTOCOLS:
   - For critical subjects (Math, Science), find best available match
   - For elective subjects, can combine classes if needed
   - Ensure all students receive instruction

OUTPUT FORMAT:
Return a JSON array of substitution recommendations. Each entry should have:
- entry_id: integer (ID of the affected timetable entry)
- substitute_teacher_id: integer (ID of the recommended substitute)
- reason: string (brief explanation for the choice)
- confidence: float (0.0 to 1.0, how confident you are in this substitution)

Return ONLY the JSON array, no additional text or explanations.
"""
    
    return prompt


"""
Export Helper utilities for Edu-Sync AI
PDF, Excel, and iCal export functionality
"""

import pandas as pd
import io
import tempfile
import os
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import icalendar
from models import db, TimetableEntry, ExamSchedule, ExamAssignment, User

class ExportHelper:
    def __init__(self):
        """Initialize export helper"""
        self.temp_dir = tempfile.mkdtemp()
    
    def export_timetable(self, format_type='pdf', version='latest', grade=None, section=None):
        """Export timetable in specified format"""
        try:
            # Get timetable entries
            query = TimetableEntry.query
            if version != 'latest':
                query = query.filter(TimetableEntry.timetable_version == version)
            if grade:
                query = query.filter(TimetableEntry.grade == grade)
            if section:
                query = query.filter(TimetableEntry.section == section)
            
            entries = query.order_by(TimetableEntry.day_of_week, TimetableEntry.time_slot).all()
            
            if format_type == 'pdf':
                return self._export_timetable_pdf(entries, grade, section)
            elif format_type == 'excel':
                return self._export_timetable_excel(entries, grade, section)
            elif format_type == 'ical':
                return self._export_timetable_ical(entries, grade, section)
            else:
                raise ValueError(f"Unsupported format: {format_type}")
                
        except Exception as e:
            raise Exception(f"Export failed: {str(e)}")
    
    def export_exam_schedule(self, format_type='pdf', grade=None):
        """Export exam schedule in specified format"""
        try:
            # Get exam schedules
            query = ExamSchedule.query
            if grade:
                query = query.filter(ExamSchedule.grade == grade)
            
            exams = query.order_by(ExamSchedule.exam_date, ExamSchedule.start_time).all()
            
            if format_type == 'pdf':
                return self._export_exam_schedule_pdf(exams, grade)
            elif format_type == 'excel':
                return self._export_exam_schedule_excel(exams, grade)
            elif format_type == 'ical':
                return self._export_exam_schedule_ical(exams, grade)
            else:
                raise ValueError(f"Unsupported format: {format_type}")
                
        except Exception as e:
            raise Exception(f"Export failed: {str(e)}")
    
    def generate_ical_export(self, user):
        """Generate iCal export for user's calendar"""
        try:
            cal = icalendar.Calendar()
            cal.add('prodid', '-//Edu-Sync AI//Timetable//EN')
            cal.add('version', '2.0')
            
            if user.role == 'teacher':
                # Get teacher's timetable
                from models import Teacher
                teacher = Teacher.query.filter_by(user_id=user.id).first()
                if teacher:
                    entries = TimetableEntry.query.filter_by(teacher_id=teacher.id).all()
                    for entry in entries:
                        event = self._create_timetable_event(entry)
                        cal.add_component(event)
            
            elif user.role == 'student':
                # Get student's timetable
                from models import Student
                student = Student.query.filter_by(user_id=user.id).first()
                if student:
                    entries = TimetableEntry.query.filter_by(
                        grade=student.grade,
                        section=student.section
                    ).all()
                    for entry in entries:
                        event = self._create_timetable_event(entry)
                        cal.add_component(event)
            
            # Add exam events
            if user.role in ['student', 'teacher']:
                grade = None
                if user.role == 'student':
                    student = Student.query.filter_by(user_id=user.id).first()
                    if student:
                        grade = student.grade
                
                exams = ExamSchedule.query
                if grade:
                    exams = exams.filter_by(grade=grade)
                
                for exam in exams.all():
                    event = self._create_exam_event(exam)
                    cal.add_component(event)
            
            # Save to temporary file
            filename = f"timetable_{user.username}_{datetime.now().strftime('%Y%m%d')}.ics"
            filepath = os.path.join(self.temp_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(cal.to_ical())
            
            return filepath
            
        except Exception as e:
            raise Exception(f"iCal export failed: {str(e)}")
    
    def _export_timetable_pdf(self, entries, grade=None, section=None):
        """Export timetable as PDF"""
        filename = f"timetable_{grade or 'all'}_{section or 'all'}_{datetime.now().strftime('%Y%m%d')}.pdf"
        filepath = os.path.join(self.temp_dir, filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        title_text = "Timetable"
        if grade and section:
            title_text += f" - Grade {grade}, Section {section}"
        elif grade:
            title_text += f" - Grade {grade}"
        
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 12))
        
        # Group entries by day
        timetable_by_day = {}
        for entry in entries:
            day = entry.day_of_week
            if day not in timetable_by_day:
                timetable_by_day[day] = []
            timetable_by_day[day].append(entry)
        
        # Create table for each day
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        for day in days:
            if day in timetable_by_day:
                story.append(Paragraph(f"<b>{day}</b>", styles['Heading2']))
                
                # Create table data
                table_data = [['Time', 'Subject', 'Teacher', 'Room', 'Grade/Section']]
                
                for entry in sorted(timetable_by_day[day], key=lambda x: x.time_slot):
                    table_data.append([
                        entry.time_slot,
                        entry.subject.name if entry.subject else 'N/A',
                        entry.teacher.user.get_full_name() if entry.teacher else 'N/A',
                        entry.room.room_number if entry.room else 'N/A',
                        f"{entry.grade}/{entry.section}"
                    ])
                
                # Create table
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(table)
                story.append(Spacer(1, 20))
        
        doc.build(story)
        return filepath
    
    def _export_timetable_excel(self, entries, grade=None, section=None):
        """Export timetable as Excel"""
        filename = f"timetable_{grade or 'all'}_{section or 'all'}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        filepath = os.path.join(self.temp_dir, filename)
        
        # Prepare data
        data = []
        for entry in entries:
            data.append({
                'Day': entry.day_of_week,
                'Time Slot': entry.time_slot,
                'Subject': entry.subject.name if entry.subject else 'N/A',
                'Teacher': entry.teacher.user.get_full_name() if entry.teacher else 'N/A',
                'Room': entry.room.room_number if entry.room else 'N/A',
                'Grade': entry.grade,
                'Section': entry.section,
                'Version': entry.timetable_version
            })
        
        df = pd.DataFrame(data)
        df.to_excel(filepath, index=False, sheet_name='Timetable')
        
        return filepath
    
    def _export_timetable_ical(self, entries, grade=None, section=None):
        """Export timetable as iCal"""
        cal = icalendar.Calendar()
        cal.add('prodid', '-//Edu-Sync AI//Timetable//EN')
        cal.add('version', '2.0')
        
        for entry in entries:
            event = self._create_timetable_event(entry)
            cal.add_component(event)
        
        filename = f"timetable_{grade or 'all'}_{section or 'all'}_{datetime.now().strftime('%Y%m%d')}.ics"
        filepath = os.path.join(self.temp_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(cal.to_ical())
        
        return filepath
    
    def _export_exam_schedule_pdf(self, exams, grade=None):
        """Export exam schedule as PDF"""
        filename = f"exam_schedule_{grade or 'all'}_{datetime.now().strftime('%Y%m%d')}.pdf"
        filepath = os.path.join(self.temp_dir, filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        title_text = "Exam Schedule"
        if grade:
            title_text += f" - Grade {grade}"
        
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 12))
        
        # Create table data
        table_data = [['Date', 'Time', 'Subject', 'Grade', 'Duration', 'Type']]
        
        for exam in exams:
            table_data.append([
                exam.exam_date.strftime('%Y-%m-%d'),
                f"{exam.start_time.strftime('%H:%M')} - {exam.end_time.strftime('%H:%M')}",
                exam.subject.name if exam.subject else 'N/A',
                exam.grade,
                f"{exam.duration_minutes} minutes",
                exam.exam_type
            ])
        
        # Create table
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        doc.build(story)
        
        return filepath
    
    def _export_exam_schedule_excel(self, exams, grade=None):
        """Export exam schedule as Excel"""
        filename = f"exam_schedule_{grade or 'all'}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        filepath = os.path.join(self.temp_dir, filename)
        
        # Prepare data
        data = []
        for exam in exams:
            data.append({
                'Date': exam.exam_date.strftime('%Y-%m-%d'),
                'Start Time': exam.start_time.strftime('%H:%M'),
                'End Time': exam.end_time.strftime('%H:%M'),
                'Subject': exam.subject.name if exam.subject else 'N/A',
                'Grade': exam.grade,
                'Duration (minutes)': exam.duration_minutes,
                'Type': exam.exam_type
            })
        
        df = pd.DataFrame(data)
        df.to_excel(filepath, index=False, sheet_name='Exam Schedule')
        
        return filepath
    
    def _export_exam_schedule_ical(self, exams, grade=None):
        """Export exam schedule as iCal"""
        cal = icalendar.Calendar()
        cal.add('prodid', '-//Edu-Sync AI//Exam Schedule//EN')
        cal.add('version', '2.0')
        
        for exam in exams:
            event = self._create_exam_event(exam)
            cal.add_component(event)
        
        filename = f"exam_schedule_{grade or 'all'}_{datetime.now().strftime('%Y%m%d')}.ics"
        filepath = os.path.join(self.temp_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(cal.to_ical())
        
        return filepath
    
    def _create_timetable_event(self, entry):
        """Create iCal event for timetable entry"""
        event = icalendar.Event()
        
        # Set basic properties
        event.add('summary', f"{entry.subject.name if entry.subject else 'Class'}")
        event.add('description', f"Teacher: {entry.teacher.user.get_full_name() if entry.teacher else 'N/A'}\\nRoom: {entry.room.room_number if entry.room else 'N/A'}")
        event.add('location', entry.room.room_number if entry.room else 'TBA')
        
        # Set time (assuming current week for recurring events)
        start_time, end_time = entry.time_slot.split('-')
        
        # Get next occurrence of this day
        today = datetime.now().date()
        days_ahead = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'].index(entry.day_of_week)
        target_date = today + timedelta(days=(days_ahead - today.weekday()) % 7)
        
        start_datetime = datetime.combine(target_date, datetime.strptime(start_time, '%H:%M').time())
        end_datetime = datetime.combine(target_date, datetime.strptime(end_time, '%H:%M').time())
        
        event.add('dtstart', start_datetime)
        event.add('dtend', end_datetime)
        
        # Set recurrence (weekly)
        event.add('rrule', {'freq': 'weekly', 'byday': entry.day_of_week[:2].upper()})
        
        return event
    
    def _create_exam_event(self, exam):
        """Create iCal event for exam"""
        event = icalendar.Event()
        
        # Set basic properties
        event.add('summary', f"Exam: {exam.subject.name if exam.subject else 'Exam'}")
        event.add('description', f"Grade: {exam.grade}\\nType: {exam.exam_type}\\nDuration: {exam.duration_minutes} minutes")
        event.add('location', 'Exam Hall')
        
        # Set time
        start_datetime = datetime.combine(exam.exam_date, exam.start_time)
        end_datetime = datetime.combine(exam.exam_date, exam.end_time)
        
        event.add('dtstart', start_datetime)
        event.add('dtend', end_datetime)
        
        # Set priority (high for exams)
        event.add('priority', 9)
        
        return event
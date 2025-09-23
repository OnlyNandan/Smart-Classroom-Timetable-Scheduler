"""
Authentication routes for Edu-Sync AI
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from models import db, User, Teacher, Student, Parent
from datetime import datetime
import re

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if user.is_active:
                login_user(user, remember=remember)
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                flash(f'Welcome back, {user.get_full_name()}!', 'success')
                
                # Redirect based on role
                if user.role == 'admin':
                    return redirect(url_for('admin.dashboard'))
                elif user.role == 'teacher':
                    return redirect(url_for('teacher.dashboard'))
                elif user.role == 'student':
                    return redirect(url_for('student.dashboard'))
                elif user.role == 'parent':
                    return redirect(url_for('parent.dashboard'))
                else:
                    return redirect(url_for('index'))
            else:
                flash('Your account has been deactivated. Please contact administrator.', 'error')
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        role = request.form.get('role')
        phone = request.form.get('phone')
        
        # Validation
        if not all([username, email, password, first_name, last_name, role]):
            flash('All fields are required.', 'error')
            return render_template('auth/register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('auth/register.html')
        
        if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            flash('Please enter a valid email address.', 'error')
            return render_template('auth/register.html')
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return render_template('auth/register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('auth/register.html')
        
        # Create user
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            phone=phone
        )
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            # Create role-specific profile
            if role == 'teacher':
                teacher = Teacher(
                    user_id=user.id,
                    employee_id=f"T{user.id:04d}",
                    max_hours_week=40
                )
                db.session.add(teacher)
            elif role == 'student':
                student = Student(
                    user_id=user.id,
                    student_id=f"S{user.id:04d}",
                    grade=request.form.get('grade', '1'),
                    section=request.form.get('section', 'A')
                )
                db.session.add(student)
            elif role == 'parent':
                parent = Parent(
                    user_id=user.id,
                    occupation=request.form.get('occupation', ''),
                    address=request.form.get('address', '')
                )
                db.session.add(parent)
            
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
            print(f"Registration error: {str(e)}")
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # In a real application, you would send an email with reset link
            flash('Password reset instructions have been sent to your email.', 'info')
        else:
            flash('Email not found.', 'error')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
            return render_template('auth/change_password.html')
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('auth/change_password.html')
        
        if len(new_password) < 8:
            flash('New password must be at least 8 characters long.', 'error')
            return render_template('auth/change_password.html')
        
        current_user.set_password(new_password)
        db.session.commit()
        flash('Password changed successfully.', 'success')
        return redirect(url_for('index'))
    
    return render_template('auth/change_password.html')

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        current_user.phone = request.form.get('phone')
        
        # Update role-specific profile
        if current_user.role == 'teacher' and current_user.teacher_profile:
            current_user.teacher_profile.specialization = request.form.get('specialization')
            current_user.teacher_profile.qualifications = request.form.get('qualifications')
        elif current_user.role == 'parent' and current_user.parent_profile:
            current_user.parent_profile.occupation = request.form.get('occupation')
            current_user.parent_profile.address = request.form.get('address')
        
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/profile.html')
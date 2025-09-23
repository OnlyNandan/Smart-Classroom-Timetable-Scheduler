from flask import Blueprint, jsonify, request, session, redirect, url_for, render_template

from extensions import db
from models import Classroom
from utils import log_activity

classrooms_bp = Blueprint('classrooms', __name__, url_prefix='/classrooms')

@classrooms_bp.route('/')
def manage_classrooms():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    return render_template('classrooms.html')

@classrooms_bp.route('/api', methods=['GET', 'POST'])
@classrooms_bp.route('/api/<int:classroom_id>', methods=['PUT', 'DELETE'])
def handle_classrooms(classroom_id=None):
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
    try:
        if request.method == 'GET':
            classrooms = Classroom.query.order_by(Classroom.room_id).all()
            return jsonify({"classrooms": [
                {"id": c.id, "room_id": c.room_id, "capacity": c.capacity, "features": c.features or []} for c in classrooms
            ]})

        data = request.json
        if not data.get('room_id') or not data.get('capacity'):
            return jsonify({"message": "Room ID and Capacity are required fields."}), 400

        if request.method == 'POST':
            if Classroom.query.filter_by(room_id=data['room_id']).first():
                return jsonify({"message": f"Classroom with ID '{data['room_id']}' already exists."}), 409
            
            new_classroom = Classroom(room_id=data['room_id'], capacity=data['capacity'], features=data.get('features', []))
            db.session.add(new_classroom)
            log_activity('info', f"Classroom '{data['room_id']}' created.")
            message = "Classroom created successfully."

        else: # PUT or DELETE
            classroom = Classroom.query.get_or_404(classroom_id)
            if request.method == 'PUT':
                if classroom.room_id != data['room_id'] and Classroom.query.filter_by(room_id=data['room_id']).first():
                    return jsonify({"message": f"Classroom with ID '{data['room_id']}' already exists."}), 409
                
                classroom.room_id = data['room_id']
                classroom.capacity = data['capacity']
                classroom.features = data.get('features', [])
                log_activity('info', f"Classroom '{classroom.room_id}' updated.")
                message = "Classroom updated successfully."
            
            elif request.method == 'DELETE':
                db.session.delete(classroom)
                log_activity('warning', f"Classroom '{classroom.room_id}' deleted.")
                message = "Classroom deleted successfully."
        
        db.session.commit()
        return jsonify({"message": message})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "An unexpected server error occurred."}), 500

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import Room, HealthCheck, TestCall, Alert
from app import db
from utils import admin_required, log_audit_action
from sqlalchemy import desc
import logging

rooms_bp = Blueprint('rooms', __name__, url_prefix='/rooms')

@rooms_bp.route('/')
@login_required
def index():
    rooms = Room.query.order_by(Room.name).all()
    
    # Add health check and call statistics for each room
    for room in rooms:
        # Get latest health check
        latest_health_check = HealthCheck.query.filter_by(room_id=room.id)\
            .order_by(desc(HealthCheck.timestamp))\
            .first()
        room.latest_health_check = latest_health_check
        
        # Get latest test call
        latest_test_call = TestCall.query.filter_by(room_id=room.id)\
            .order_by(desc(TestCall.timestamp))\
            .first()
        room.latest_test_call = latest_test_call
        
        # Count open alerts
        room.open_alerts_count = Alert.query.filter_by(room_id=room.id, status='open').count()
    
    return render_template('rooms/index.html', rooms=rooms)

@rooms_bp.route('/add', methods=['GET', 'POST'])
@admin_required
def add():
    if request.method == 'POST':
        name = request.form.get('name')
        location = request.form.get('location', '')
        ip_address = request.form.get('ip_address', '')
        room_id = request.form.get('room_id')
        device_type = request.form.get('device_type', 'RoomOS')
        health_check_enabled = bool(request.form.get('health_check_enabled'))
        test_call_enabled = bool(request.form.get('test_call_enabled'))
        test_call_time = request.form.get('test_call_time', '07:00')
        
        if not name or not room_id:
            flash('Room name and Room ID are required.', 'error')
            return render_template('rooms/add.html')
        
        # Check if room_id already exists
        existing_room = Room.query.filter_by(room_id=room_id).first()
        if existing_room:
            flash('A room with this Room ID already exists.', 'error')
            return render_template('rooms/add.html')
        
        try:
            room = Room(
                name=name,
                location=location,
                ip_address=ip_address,
                room_id=room_id,
                device_type=device_type,
                health_check_enabled=health_check_enabled,
                test_call_enabled=test_call_enabled,
                test_call_time=test_call_time
            )
            
            db.session.add(room)
            db.session.commit()
            
            log_audit_action('create', 'room', room.id, f"Added room: {name}")
            flash(f'Room "{name}" has been added successfully.', 'success')
            logging.info(f"Room {name} added by admin")
            
            return redirect(url_for('rooms.index'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while adding the room.', 'error')
            logging.error(f"Error adding room: {e}")
    
    return render_template('rooms/add.html')

@rooms_bp.route('/<int:room_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit(room_id):
    room = Room.query.get_or_404(room_id)
    
    if request.method == 'POST':
        room.name = request.form.get('name')
        room.location = request.form.get('location', '')
        room.ip_address = request.form.get('ip_address', '')
        room.room_id = request.form.get('room_id')
        room.device_type = request.form.get('device_type', 'RoomOS')
        room.health_check_enabled = bool(request.form.get('health_check_enabled'))
        room.test_call_enabled = bool(request.form.get('test_call_enabled'))
        room.test_call_time = request.form.get('test_call_time', '07:00')
        
        if not room.name or not room.room_id:
            flash('Room name and Room ID are required.', 'error')
            return render_template('rooms/edit.html', room=room)
        
        # Check if room_id already exists (excluding current room)
        existing_room = Room.query.filter_by(room_id=room.room_id).filter(Room.id != room_id).first()
        if existing_room:
            flash('A room with this Room ID already exists.', 'error')
            return render_template('rooms/edit.html', room=room)
        
        try:
            db.session.commit()
            
            log_audit_action('update', 'room', room.id, f"Updated room: {room.name}")
            flash(f'Room "{room.name}" has been updated successfully.', 'success')
            logging.info(f"Room {room.name} updated by admin")
            
            return redirect(url_for('rooms.index'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating the room.', 'error')
            logging.error(f"Error updating room: {e}")
    
    return render_template('rooms/edit.html', room=room)

@rooms_bp.route('/<int:room_id>/delete', methods=['POST'])
@admin_required
def delete(room_id):
    room = Room.query.get_or_404(room_id)
    room_name = room.name
    
    try:
        # Delete related records first
        HealthCheck.query.filter_by(room_id=room_id).delete()
        TestCall.query.filter_by(room_id=room_id).delete()
        Alert.query.filter_by(room_id=room_id).delete()
        
        db.session.delete(room)
        db.session.commit()
        
        log_audit_action('delete', 'room', room_id, f"Deleted room: {room_name}")
        flash(f'Room "{room_name}" has been deleted successfully.', 'success')
        logging.info(f"Room {room_name} deleted by admin")
        
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the room.', 'error')
        logging.error(f"Error deleting room: {e}")
    
    return redirect(url_for('rooms.index'))

@rooms_bp.route('/<int:room_id>/details')
@login_required
def details(room_id):
    room = Room.query.get_or_404(room_id)
    
    # Get recent health checks
    health_checks = HealthCheck.query.filter_by(room_id=room_id)\
        .order_by(desc(HealthCheck.timestamp))\
        .limit(20)\
        .all()
    
    # Get recent test calls
    test_calls = TestCall.query.filter_by(room_id=room_id)\
        .order_by(desc(TestCall.timestamp))\
        .limit(20)\
        .all()
    
    # Get recent alerts
    alerts = Alert.query.filter_by(room_id=room_id)\
        .order_by(desc(Alert.timestamp))\
        .limit(20)\
        .all()
    
    return render_template('rooms/details.html',
                         room=room,
                         health_checks=health_checks,
                         test_calls=test_calls,
                         alerts=alerts)

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from models import Room, HealthCheck, TestCall, Alert
from app import db
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from services.webex_api import WebexAPI
from services.roomos_api import RoomOSAPI
import logging

monitoring_bp = Blueprint('monitoring', __name__, url_prefix='/monitoring')

@monitoring_bp.route('/health-checks')
@login_required
def health_checks():
    page = request.args.get('page', 1, type=int)
    room_id = request.args.get('room_id', type=int)
    status = request.args.get('status')
    
    query = db.session.query(HealthCheck).join(Room)
    
    if room_id:
        query = query.filter(HealthCheck.room_id == room_id)
    
    if status:
        query = query.filter(HealthCheck.status == status)
    
    health_checks = query.order_by(desc(HealthCheck.timestamp))\
        .paginate(page=page, per_page=50, error_out=False)
    
    rooms = Room.query.order_by(Room.name).all()
    
    return render_template('monitoring/health_checks.html',
                         health_checks=health_checks,
                         rooms=rooms,
                         selected_room_id=room_id,
                         selected_status=status)

@monitoring_bp.route('/call-quality')
@login_required
def call_quality():
    page = request.args.get('page', 1, type=int)
    room_id = request.args.get('room_id', type=int)
    status = request.args.get('status')
    
    query = db.session.query(TestCall).join(Room)
    
    if room_id:
        query = query.filter(TestCall.room_id == room_id)
    
    if status:
        query = query.filter(TestCall.status == status)
    
    test_calls = query.order_by(desc(TestCall.timestamp))\
        .paginate(page=page, per_page=50, error_out=False)
    
    rooms = Room.query.order_by(Room.name).all()
    
    # Calculate quality statistics
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    quality_stats = db.session.query(
        func.avg(TestCall.packet_loss_percent).label('avg_packet_loss'),
        func.avg(TestCall.jitter_ms).label('avg_jitter'),
        func.avg(TestCall.latency_ms).label('avg_latency'),
        func.count(TestCall.id).label('total_calls'),
        func.sum(func.case([(TestCall.status == 'completed', 1)], else_=0)).label('successful_calls')
    ).filter(TestCall.timestamp >= seven_days_ago).first()
    
    return render_template('monitoring/call_quality.html',
                         test_calls=test_calls,
                         rooms=rooms,
                         selected_room_id=room_id,
                         selected_status=status,
                         quality_stats=quality_stats)

@monitoring_bp.route('/run-health-check/<int:room_id>', methods=['POST'])
@login_required
def run_health_check(room_id):
    """Manually trigger health check for a specific room"""
    room = Room.query.get_or_404(room_id)
    
    try:
        # Import here to avoid circular imports
        from services.scheduler import perform_health_check
        result = perform_health_check(room_id)
        
        if result['success']:
            flash(f'Health check completed for room "{room.name}".', 'success')
        else:
            flash(f'Health check failed for room "{room.name}": {result.get("error", "Unknown error")}', 'error')
    
    except Exception as e:
        flash(f'Error running health check: {str(e)}', 'error')
        logging.error(f"Manual health check error for room {room_id}: {e}")
    
    return redirect(request.referrer or url_for('monitoring.health_checks'))

@monitoring_bp.route('/run-test-call/<int:room_id>', methods=['POST'])
@login_required
def run_test_call(room_id):
    """Manually trigger test call for a specific room"""
    room = Room.query.get_or_404(room_id)
    
    try:
        # Import here to avoid circular imports
        from services.scheduler import perform_test_call
        result = perform_test_call(room_id)
        
        if result['success']:
            flash(f'Test call initiated for room "{room.name}".', 'success')
        else:
            flash(f'Test call failed for room "{room.name}": {result.get("error", "Unknown error")}', 'error')
    
    except Exception as e:
        flash(f'Error running test call: {str(e)}', 'error')
        logging.error(f"Manual test call error for room {room_id}: {e}")
    
    return redirect(request.referrer or url_for('monitoring.call_quality'))

@monitoring_bp.route('/api/health-check-trends/<int:room_id>')
@login_required
def api_health_check_trends(room_id):
    """API endpoint for health check trends data"""
    days = request.args.get('days', 30, type=int)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    health_checks = HealthCheck.query.filter(
        HealthCheck.room_id == room_id,
        HealthCheck.timestamp >= start_date
    ).order_by(HealthCheck.timestamp).all()
    
    trends_data = []
    for check in health_checks:
        trends_data.append({
            'timestamp': check.timestamp.isoformat(),
            'status': check.status,
            'device_online': check.device_online,
            'temperature': check.temperature,
            'uptime_hours': check.uptime_hours
        })
    
    return jsonify(trends_data)

@monitoring_bp.route('/api/call-quality-trends/<int:room_id>')
@login_required
def api_call_quality_trends(room_id):
    """API endpoint for call quality trends data"""
    days = request.args.get('days', 30, type=int)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    test_calls = TestCall.query.filter(
        TestCall.room_id == room_id,
        TestCall.timestamp >= start_date,
        TestCall.status == 'completed'
    ).order_by(TestCall.timestamp).all()
    
    trends_data = []
    for call in test_calls:
        trends_data.append({
            'timestamp': call.timestamp.isoformat(),
            'packet_loss_percent': call.packet_loss_percent,
            'jitter_ms': call.jitter_ms,
            'latency_ms': call.latency_ms,
            'call_quality_score': call.call_quality_score
        })
    
    return jsonify(trends_data)

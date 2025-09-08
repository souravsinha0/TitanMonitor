from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from models import Room, HealthCheck, TestCall, Alert
from app import db
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import logging

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    # Get summary statistics
    total_rooms = Room.query.count()
    online_rooms = Room.query.filter_by(status='online').count()
    offline_rooms = Room.query.filter_by(status='offline').count()
    
    # Get recent health checks
    recent_health_checks = db.session.query(HealthCheck)\
        .join(Room)\
        .order_by(desc(HealthCheck.timestamp))\
        .limit(10)\
        .all()
    
    # Get recent test calls
    recent_test_calls = db.session.query(TestCall)\
        .join(Room)\
        .order_by(desc(TestCall.timestamp))\
        .limit(10)\
        .all()
    
    # Get open alerts
    open_alerts = Alert.query.filter_by(status='open')\
        .order_by(desc(Alert.timestamp))\
        .limit(10)\
        .all()
    
    # Calculate uptime percentage for last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    uptime_data = db.session.query(
        Room.name,
        func.count(HealthCheck.id).label('total_checks'),
        func.sum(func.case([(HealthCheck.device_online == True, 1)], else_=0)).label('online_checks')
    ).join(HealthCheck)\
     .filter(HealthCheck.timestamp >= thirty_days_ago)\
     .group_by(Room.id, Room.name)\
     .all()
    
    # Calculate call quality statistics for last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    call_quality_stats = db.session.query(
        func.avg(TestCall.packet_loss_percent).label('avg_packet_loss'),
        func.avg(TestCall.jitter_ms).label('avg_jitter'),
        func.avg(TestCall.latency_ms).label('avg_latency'),
        func.count(TestCall.id).label('total_calls'),
        func.sum(func.case([(TestCall.status == 'completed', 1)], else_=0)).label('successful_calls')
    ).filter(TestCall.timestamp >= seven_days_ago).first()
    
    return render_template('dashboard/index.html',
                         total_rooms=total_rooms,
                         online_rooms=online_rooms,
                         offline_rooms=offline_rooms,
                         recent_health_checks=recent_health_checks,
                         recent_test_calls=recent_test_calls,
                         open_alerts=open_alerts,
                         uptime_data=uptime_data,
                         call_quality_stats=call_quality_stats)

@dashboard_bp.route('/api/room-status')
@login_required
def api_room_status():
    """API endpoint for real-time room status updates"""
    rooms = Room.query.all()
    room_status = []
    
    for room in rooms:
        # Get latest health check
        latest_health_check = HealthCheck.query.filter_by(room_id=room.id)\
            .order_by(desc(HealthCheck.timestamp))\
            .first()
        
        # Get latest test call
        latest_test_call = TestCall.query.filter_by(room_id=room.id)\
            .order_by(desc(TestCall.timestamp))\
            .first()
        
        room_data = {
            'id': room.id,
            'name': room.name,
            'location': room.location,
            'status': room.status,
            'last_health_check': latest_health_check.timestamp.isoformat() if latest_health_check else None,
            'health_status': latest_health_check.status if latest_health_check else 'unknown',
            'last_test_call': latest_test_call.timestamp.isoformat() if latest_test_call else None,
            'call_quality': latest_test_call.call_quality_score if latest_test_call else None
        }
        room_status.append(room_data)
    
    return jsonify(room_status)

@dashboard_bp.route('/api/alerts-summary')
@login_required
def api_alerts_summary():
    """API endpoint for alerts summary"""
    alerts_by_severity = db.session.query(
        Alert.severity,
        func.count(Alert.id).label('count')
    ).filter_by(status='open')\
     .group_by(Alert.severity)\
     .all()
    
    alerts_summary = {
        'total_open': Alert.query.filter_by(status='open').count(),
        'by_severity': {severity: count for severity, count in alerts_by_severity}
    }
    
    return jsonify(alerts_summary)

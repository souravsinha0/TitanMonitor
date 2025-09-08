from flask import Blueprint, render_template, request, make_response, send_file
from flask_login import login_required
from models import Room, HealthCheck, TestCall, Alert
from app import db
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import csv
import io
import logging

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@login_required
def index():
    # Get date range from request parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    room_id = request.args.get('room_id', type=int)
    
    # Default to last 30 days if no date range specified
    if not start_date_str or not end_date_str:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
    
    # Build base queries
    health_check_query = HealthCheck.query.filter(
        HealthCheck.timestamp >= start_date,
        HealthCheck.timestamp <= end_date
    )
    
    test_call_query = TestCall.query.filter(
        TestCall.timestamp >= start_date,
        TestCall.timestamp <= end_date
    )
    
    alert_query = Alert.query.filter(
        Alert.timestamp >= start_date,
        Alert.timestamp <= end_date
    )
    
    if room_id:
        health_check_query = health_check_query.filter(HealthCheck.room_id == room_id)
        test_call_query = test_call_query.filter(TestCall.room_id == room_id)
        alert_query = alert_query.filter(Alert.room_id == room_id)
    
    # Health check statistics
    health_check_stats = health_check_query.with_entities(
        func.count(HealthCheck.id).label('total_checks'),
        func.sum(func.case([(HealthCheck.status == 'pass', 1)], else_=0)).label('passed_checks'),
        func.sum(func.case([(HealthCheck.device_online == True, 1)], else_=0)).label('online_checks')
    ).first()
    
    # Test call statistics
    test_call_stats = test_call_query.with_entities(
        func.count(TestCall.id).label('total_calls'),
        func.sum(func.case([(TestCall.status == 'completed', 1)], else_=0)).label('completed_calls'),
        func.avg(TestCall.packet_loss_percent).label('avg_packet_loss'),
        func.avg(TestCall.jitter_ms).label('avg_jitter'),
        func.avg(TestCall.latency_ms).label('avg_latency')
    ).first()
    
    # Alert statistics
    alert_stats = alert_query.with_entities(
        func.count(Alert.id).label('total_alerts'),
        func.sum(func.case([(Alert.severity == 'critical', 1)], else_=0)).label('critical_alerts'),
        func.sum(func.case([(Alert.severity == 'high', 1)], else_=0)).label('high_alerts'),
        func.sum(func.case([(Alert.status == 'resolved', 1)], else_=0)).label('resolved_alerts')
    ).first()
    
    # Room-wise statistics
    room_stats = db.session.query(
        Room.name,
        Room.id,
        func.count(HealthCheck.id).label('health_checks'),
        func.sum(func.case([(HealthCheck.status == 'pass', 1)], else_=0)).label('passed_checks'),
        func.count(TestCall.id).label('test_calls'),
        func.sum(func.case([(TestCall.status == 'completed', 1)], else_=0)).label('completed_calls')
    ).outerjoin(HealthCheck, (Room.id == HealthCheck.room_id) & 
                (HealthCheck.timestamp >= start_date) & 
                (HealthCheck.timestamp <= end_date))\
     .outerjoin(TestCall, (Room.id == TestCall.room_id) & 
                (TestCall.timestamp >= start_date) & 
                (TestCall.timestamp <= end_date))\
     .group_by(Room.id, Room.name)\
     .order_by(Room.name)\
     .all()
    
    rooms = Room.query.order_by(Room.name).all()
    
    return render_template('reports/index.html',
                         health_check_stats=health_check_stats,
                         test_call_stats=test_call_stats,
                         alert_stats=alert_stats,
                         room_stats=room_stats,
                         rooms=rooms,
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=(end_date - timedelta(days=1)).strftime('%Y-%m-%d'),
                         selected_room_id=room_id)

@reports_bp.route('/export/health-checks')
@login_required
def export_health_checks():
    """Export health check data to CSV"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    room_id = request.args.get('room_id', type=int)
    
    # Default to last 30 days if no date range specified
    if not start_date_str or not end_date_str:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
    
    query = db.session.query(HealthCheck, Room.name)\
        .join(Room)\
        .filter(HealthCheck.timestamp >= start_date,
                HealthCheck.timestamp <= end_date)
    
    if room_id:
        query = query.filter(HealthCheck.room_id == room_id)
    
    health_checks = query.order_by(desc(HealthCheck.timestamp)).all()
    
    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Room Name', 'Timestamp', 'Status', 'Device Online', 
        'Camera Status', 'Microphone Status', 'Speaker Status',
        'Software Version', 'Uptime Hours', 'Temperature', 'Error Message'
    ])
    
    # Write data
    for health_check, room_name in health_checks:
        writer.writerow([
            room_name,
            health_check.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            health_check.status,
            'Yes' if health_check.device_online else 'No',
            health_check.camera_status or 'Unknown',
            health_check.microphone_status or 'Unknown',
            health_check.speaker_status or 'Unknown',
            health_check.software_version or 'Unknown',
            health_check.uptime_hours or 0,
            health_check.temperature or 'Unknown',
            health_check.error_message or ''
        ])
    
    # Create response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=health_checks_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.csv'
    
    return response

@reports_bp.route('/export/test-calls')
@login_required
def export_test_calls():
    """Export test call data to CSV"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    room_id = request.args.get('room_id', type=int)
    
    # Default to last 30 days if no date range specified
    if not start_date_str or not end_date_str:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
    
    query = db.session.query(TestCall, Room.name)\
        .join(Room)\
        .filter(TestCall.timestamp >= start_date,
                TestCall.timestamp <= end_date)
    
    if room_id:
        query = query.filter(TestCall.room_id == room_id)
    
    test_calls = query.order_by(desc(TestCall.timestamp)).all()
    
    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Room Name', 'Timestamp', 'Call ID', 'Duration (seconds)', 'Status',
        'Call Quality Score', 'Packet Loss (%)', 'Jitter (ms)', 'Latency (ms)',
        'Resolution', 'Frame Rate', 'Audio Quality', 'Video Quality', 'Error Message'
    ])
    
    # Write data
    for test_call, room_name in test_calls:
        writer.writerow([
            room_name,
            test_call.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            test_call.call_id or '',
            test_call.duration_seconds or 0,
            test_call.status,
            test_call.call_quality_score or 0,
            test_call.packet_loss_percent or 0,
            test_call.jitter_ms or 0,
            test_call.latency_ms or 0,
            test_call.resolution or 'Unknown',
            test_call.frame_rate or 0,
            test_call.audio_quality or 'Unknown',
            test_call.video_quality or 'Unknown',
            test_call.error_message or ''
        ])
    
    # Create response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=test_calls_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.csv'
    
    return response

@reports_bp.route('/export/alerts')
@login_required
def export_alerts():
    """Export alerts data to CSV"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    room_id = request.args.get('room_id', type=int)
    
    # Default to last 30 days if no date range specified
    if not start_date_str or not end_date_str:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
    
    query = db.session.query(Alert, Room.name)\
        .join(Room)\
        .filter(Alert.timestamp >= start_date,
                Alert.timestamp <= end_date)
    
    if room_id:
        query = query.filter(Alert.room_id == room_id)
    
    alerts = query.order_by(desc(Alert.timestamp)).all()
    
    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Room Name', 'Timestamp', 'Alert Type', 'Severity', 'Title',
        'Description', 'Status', 'Ticket ID', 'Resolved At'
    ])
    
    # Write data
    for alert, room_name in alerts:
        writer.writerow([
            room_name,
            alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            alert.alert_type,
            alert.severity,
            alert.title,
            alert.description,
            alert.status,
            alert.ticket_id or '',
            alert.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if alert.resolved_at else ''
        ])
    
    # Create response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=alerts_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.csv'
    
    return response

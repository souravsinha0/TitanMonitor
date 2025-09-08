from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
import logging
from app import app, db
from models import Room, HealthCheck, TestCall, Alert
from services.webex_api import WebexAPI
from services.roomos_api import RoomOSAPI
from services.notifications import NotificationService
from config import Config

scheduler = BackgroundScheduler()

def init_scheduler():
    """Initialize scheduled tasks"""
    with app.app_context():
        # Schedule daily health checks at 6 AM
        scheduler.add_job(
            func=daily_health_checks,
            trigger=CronTrigger(hour=6, minute=0),
            id='daily_health_checks',
            name='Daily Health Checks',
            replace_existing=True
        )
        
        # Schedule test calls (will be dynamic based on room configurations)
        schedule_test_calls()
        
        # Schedule cleanup of old data every week
        scheduler.add_job(
            func=cleanup_old_data,
            trigger=CronTrigger(day_of_week=0, hour=2, minute=0),  # Sunday 2 AM
            id='weekly_cleanup',
            name='Weekly Data Cleanup',
            replace_existing=True
        )
        
        logging.info("Scheduler initialized with jobs")

def schedule_test_calls():
    """Schedule test calls for all rooms based on their configuration"""
    with app.app_context():
        rooms = Room.query.filter_by(test_call_enabled=True).all()
        
        for room in rooms:
            if room.test_call_time:
                try:
                    hour, minute = room.test_call_time.split(':')
                    hour = int(hour)
                    minute = int(minute)
                    
                    job_id = f'test_call_room_{room.id}'
                    
                    scheduler.add_job(
                        func=perform_test_call,
                        args=[room.id],
                        trigger=CronTrigger(hour=hour, minute=minute),
                        id=job_id,
                        name=f'Test Call - {room.name}',
                        replace_existing=True
                    )
                    
                    logging.info(f"Scheduled test call for room {room.name} at {room.test_call_time}")
                    
                except ValueError as e:
                    logging.error(f"Invalid test call time format for room {room.name}: {e}")

def daily_health_checks():
    """Perform health checks for all enabled rooms"""
    with app.app_context():
        rooms = Room.query.filter_by(health_check_enabled=True).all()
        logging.info(f"Starting daily health checks for {len(rooms)} rooms")
        
        for room in rooms:
            try:
                result = perform_health_check(room.id)
                if result['success']:
                    logging.info(f"Health check completed for room {room.name}")
                else:
                    logging.error(f"Health check failed for room {room.name}: {result.get('error')}")
            except Exception as e:
                logging.error(f"Exception during health check for room {room.name}: {e}")

def perform_health_check(room_id):
    """Perform health check for a specific room"""
    with app.app_context():
        room = Room.query.get(room_id)
        if not room:
            return {'success': False, 'error': 'Room not found'}
        
        try:
            # Initialize RoomOS API
            roomos_api = RoomOSAPI(room.ip_address) if room.ip_address else None
            webex_api = WebexAPI()
            
            health_check = HealthCheck(room_id=room.id)
            
            if roomos_api:
                # Get device status from RoomOS
                status_result = roomos_api.get_device_status()
                
                if status_result['success']:
                    data = status_result['data']
                    
                    health_check.device_online = data.get('device_online', False)
                    health_check.camera_status = data.get('camera_status', 'unknown')
                    health_check.microphone_status = data.get('microphone_status', 'unknown')
                    health_check.speaker_status = data.get('speaker_status', 'unknown')
                    health_check.software_version = data.get('software_version')
                    health_check.uptime_hours = data.get('uptime_hours')
                    health_check.temperature = data.get('temperature')
                    
                    # Determine overall status
                    if health_check.device_online:
                        if (health_check.camera_status == 'connected' and 
                            health_check.microphone_status == 'connected' and 
                            health_check.speaker_status == 'connected'):
                            health_check.status = 'pass'
                            room.status = 'online'
                        else:
                            health_check.status = 'warning'
                            room.status = 'warning'
                    else:
                        health_check.status = 'fail'
                        room.status = 'offline'
                else:
                    health_check.status = 'fail'
                    health_check.device_online = False
                    health_check.error_message = status_result.get('error', 'Unknown error')
                    room.status = 'error'
            
            elif room.room_id:
                # Try to get status from Webex API
                device_result = webex_api.get_device_status(room.room_id)
                
                if device_result['success']:
                    device_data = device_result['device']
                    status_data = device_result['status']
                    
                    health_check.device_online = device_data.get('connectionStatus') == 'connected'
                    health_check.software_version = device_data.get('software')
                    
                    if health_check.device_online:
                        health_check.status = 'pass'
                        room.status = 'online'
                    else:
                        health_check.status = 'fail'
                        room.status = 'offline'
                else:
                    health_check.status = 'fail'
                    health_check.device_online = False
                    health_check.error_message = device_result.get('error', 'Unknown error')
                    room.status = 'error'
            
            else:
                health_check.status = 'fail'
                health_check.device_online = False
                health_check.error_message = 'No IP address or Room ID configured'
                room.status = 'error'
            
            # Update room's last health check time
            room.last_health_check = datetime.utcnow()
            
            # Save to database
            db.session.add(health_check)
            db.session.commit()
            
            # Create alert if health check failed
            if health_check.status == 'fail':
                create_alert(
                    room_id=room.id,
                    alert_type='health_check_fail',
                    severity='high',
                    title=f'Health Check Failed - {room.name}',
                    description=f'Health check failed for room {room.name}. Error: {health_check.error_message or "Device offline or unreachable"}'
                )
            
            return {'success': True, 'health_check_id': health_check.id}
            
        except Exception as e:
            logging.error(f"Error performing health check for room {room.name}: {e}")
            return {'success': False, 'error': str(e)}

def perform_test_call(room_id):
    """Perform test call for a specific room"""
    with app.app_context():
        room = Room.query.get(room_id)
        if not room:
            return {'success': False, 'error': 'Room not found'}
        
        try:
            webex_api = WebexAPI()
            roomos_api = RoomOSAPI(room.ip_address) if room.ip_address else None
            
            # Create test call record
            test_call = TestCall(
                room_id=room.id,
                status='scheduled'
            )
            db.session.add(test_call)
            db.session.commit()
            
            # Create meeting
            meeting_title = f"Test Call - {room.name} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
            start_time = datetime.utcnow()
            
            meeting_result = webex_api.create_meeting(meeting_title, start_time, Config.TEST_CALL_DURATION // 60)
            
            if not meeting_result['success']:
                test_call.status = 'failed'
                test_call.error_message = f"Failed to create meeting: {meeting_result.get('error')}"
                db.session.commit()
                return meeting_result
            
            meeting = meeting_result['meeting']
            test_call.call_id = meeting['id']
            test_call.status = 'started'
            db.session.commit()
            
            # Start call on room device if RoomOS API is available
            if roomos_api and 'webLink' in meeting:
                call_result = roomos_api.start_test_call(meeting['webLink'])
                if not call_result['success']:
                    logging.warning(f"Failed to start call on room device: {call_result.get('error')}")
            
            # Schedule call end after 2 minutes
            scheduler.add_job(
                func=end_test_call,
                args=[test_call.id],
                trigger='date',
                run_date=datetime.utcnow() + timedelta(seconds=Config.TEST_CALL_DURATION),
                id=f'end_test_call_{test_call.id}',
                replace_existing=True
            )
            
            logging.info(f"Test call started for room {room.name}")
            return {'success': True, 'test_call_id': test_call.id}
            
        except Exception as e:
            logging.error(f"Error performing test call for room {room.name}: {e}")
            
            if 'test_call' in locals():
                test_call.status = 'failed'
                test_call.error_message = str(e)
                db.session.commit()
            
            return {'success': False, 'error': str(e)}

def end_test_call(test_call_id):
    """End test call and collect quality metrics"""
    with app.app_context():
        test_call = TestCall.query.get(test_call_id)
        if not test_call:
            logging.error(f"Test call {test_call_id} not found")
            return
        
        try:
            webex_api = WebexAPI()
            roomos_api = RoomOSAPI(test_call.room.ip_address) if test_call.room.ip_address else None
            
            # End call on room device
            if roomos_api:
                roomos_api.end_call()
            
            # Calculate call duration
            if test_call.timestamp:
                duration = datetime.utcnow() - test_call.timestamp
                test_call.duration_seconds = int(duration.total_seconds())
            
            # Get call quality metrics
            if test_call.call_id:
                quality_result = webex_api.get_meeting_quality(test_call.call_id)
                
                if quality_result['success']:
                    metrics = quality_result['quality_metrics']
                    
                    test_call.packet_loss_percent = metrics.get('packet_loss_percent', 0)
                    test_call.jitter_ms = metrics.get('jitter_ms', 0)
                    test_call.latency_ms = metrics.get('latency_ms', 0)
                    test_call.call_quality_score = metrics.get('call_quality_score', 0)
                    
                    # Set resolution and frame rate (mock values for now)
                    test_call.resolution = '1920x1080'
                    test_call.frame_rate = 30
                    test_call.audio_quality = 'good'
                    test_call.video_quality = 'good'
                    
                    # Check if quality is below thresholds
                    if (test_call.packet_loss_percent > Config.DEFAULT_PACKET_LOSS_THRESHOLD or
                        test_call.jitter_ms > Config.DEFAULT_JITTER_THRESHOLD or
                        test_call.latency_ms > Config.DEFAULT_LATENCY_THRESHOLD):
                        
                        create_alert(
                            room_id=test_call.room_id,
                            alert_type='poor_call_quality',
                            severity='medium',
                            title=f'Poor Call Quality - {test_call.room.name}',
                            description=f'Call quality below threshold: Packet Loss: {test_call.packet_loss_percent}%, Jitter: {test_call.jitter_ms}ms, Latency: {test_call.latency_ms}ms'
                        )
                
                # Delete the meeting
                webex_api.delete_meeting(test_call.call_id)
            
            test_call.status = 'completed'
            db.session.commit()
            
            logging.info(f"Test call completed for room {test_call.room.name}")
            
        except Exception as e:
            logging.error(f"Error ending test call {test_call_id}: {e}")
            test_call.status = 'failed'
            test_call.error_message = str(e)
            db.session.commit()

def create_alert(room_id, alert_type, severity, title, description):
    """Create an alert for the specified room"""
    try:
        alert = Alert(
            room_id=room_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            description=description
        )
        
        db.session.add(alert)
        db.session.commit()
        
        # Send notification
        notification_service = NotificationService()
        notification_service.send_alert_notification(alert)
        
        logging.info(f"Alert created: {title}")
        
    except Exception as e:
        logging.error(f"Error creating alert: {e}")

def cleanup_old_data():
    """Clean up old data based on retention policies"""
    with app.app_context():
        try:
            cutoff_health_checks = datetime.utcnow() - timedelta(days=Config.HEALTH_CHECK_RETENTION_DAYS)
            cutoff_call_data = datetime.utcnow() - timedelta(days=Config.CALL_DATA_RETENTION_DAYS)
            cutoff_alerts = datetime.utcnow() - timedelta(days=Config.ALERT_RETENTION_DAYS)
            
            # Delete old health checks
            old_health_checks = HealthCheck.query.filter(HealthCheck.timestamp < cutoff_health_checks).count()
            HealthCheck.query.filter(HealthCheck.timestamp < cutoff_health_checks).delete()
            
            # Delete old test calls
            old_test_calls = TestCall.query.filter(TestCall.timestamp < cutoff_call_data).count()
            TestCall.query.filter(TestCall.timestamp < cutoff_call_data).delete()
            
            # Delete old resolved alerts
            old_alerts = Alert.query.filter(
                Alert.timestamp < cutoff_alerts,
                Alert.status == 'resolved'
            ).count()
            Alert.query.filter(
                Alert.timestamp < cutoff_alerts,
                Alert.status == 'resolved'
            ).delete()
            
            db.session.commit()
            
            logging.info(f"Cleaned up old data: {old_health_checks} health checks, {old_test_calls} test calls, {old_alerts} alerts")
            
        except Exception as e:
            logging.error(f"Error during data cleanup: {e}")
            db.session.rollback()

from datetime import datetime
from app import db
from flask_login import UserMixin
from sqlalchemy import func

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    ip_address = db.Column(db.String(45))
    room_id = db.Column(db.String(100), unique=True)  # Cisco Room ID
    device_type = db.Column(db.String(50))  # RoomOS, Webex Room Kit, etc.
    status = db.Column(db.String(20), default='unknown')  # online, offline, error
    last_health_check = db.Column(db.DateTime)
    health_check_enabled = db.Column(db.Boolean, default=True)
    test_call_enabled = db.Column(db.Boolean, default=True)
    test_call_time = db.Column(db.String(10), default='07:00')  # Daily test call time
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class HealthCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20))  # pass, fail, error
    device_online = db.Column(db.Boolean)
    camera_status = db.Column(db.String(20))
    microphone_status = db.Column(db.String(20))
    speaker_status = db.Column(db.String(20))
    software_version = db.Column(db.String(50))
    uptime_hours = db.Column(db.Integer)
    temperature = db.Column(db.Float)
    error_message = db.Column(db.Text)
    
    room = db.relationship('Room', backref=db.backref('health_checks', lazy=True))

class TestCall(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    call_id = db.Column(db.String(100))
    duration_seconds = db.Column(db.Integer)
    status = db.Column(db.String(20))  # scheduled, started, completed, failed
    call_quality_score = db.Column(db.Float)
    packet_loss_percent = db.Column(db.Float)
    jitter_ms = db.Column(db.Float)
    latency_ms = db.Column(db.Float)
    resolution = db.Column(db.String(20))
    frame_rate = db.Column(db.Integer)
    audio_quality = db.Column(db.String(20))
    video_quality = db.Column(db.String(20))
    error_message = db.Column(db.Text)
    
    room = db.relationship('Room', backref=db.backref('test_calls', lazy=True))

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    alert_type = db.Column(db.String(50))  # health_check_fail, poor_call_quality, device_offline
    severity = db.Column(db.String(20))  # low, medium, high, critical
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='open')  # open, acknowledged, resolved
    ticket_id = db.Column(db.String(100))  # External ticket system ID
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    room = db.relationship('Room', backref=db.backref('alerts', lazy=True))
    resolver = db.relationship('User', backref=db.backref('resolved_alerts', lazy=True))

class Configuration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(500))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    updater = db.relationship('User', backref=db.backref('config_updates', lazy=True))

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(100))
    resource_type = db.Column(db.String(50))
    resource_id = db.Column(db.String(100))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    
    user = db.relationship('User', backref=db.backref('audit_logs', lazy=True))

from datetime import datetime, timedelta
from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user
from models import AuditLog
from app import db
import logging

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin privileges required.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

def log_audit_action(action, resource_type, resource_id=None, details=None):
    """Log audit trail for admin actions"""
    try:
        audit_log = AuditLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
            ip_address=request.remote_addr if request else None
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception as e:
        logging.error(f"Failed to log audit action: {e}")

def format_duration(seconds):
    """Format duration in seconds to human readable format"""
    if not seconds:
        return "N/A"
    
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def format_timestamp(timestamp):
    """Format timestamp for display"""
    if not timestamp:
        return "Never"
    
    now = datetime.utcnow()
    diff = now - timestamp
    
    if diff.days > 0:
        return timestamp.strftime("%Y-%m-%d %H:%M")
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"

def get_status_color(status):
    """Get Bootstrap color class for status"""
    status_colors = {
        'online': 'success',
        'offline': 'danger',
        'error': 'danger',
        'warning': 'warning',
        'unknown': 'secondary',
        'pass': 'success',
        'fail': 'danger',
        'completed': 'success',
        'failed': 'danger',
        'scheduled': 'info',
        'started': 'warning',
        'open': 'danger',
        'acknowledged': 'warning',
        'resolved': 'success'
    }
    return status_colors.get(status, 'secondary')

def get_severity_color(severity):
    """Get Bootstrap color class for alert severity"""
    severity_colors = {
        'low': 'info',
        'medium': 'warning',
        'high': 'danger',
        'critical': 'danger'
    }
    return severity_colors.get(severity, 'secondary')

def calculate_uptime_percentage(room, days=30):
    """Calculate room uptime percentage over specified days"""
    from models import HealthCheck
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    health_checks = HealthCheck.query.filter(
        HealthCheck.room_id == room.id,
        HealthCheck.timestamp >= start_date
    ).all()
    
    if not health_checks:
        return None
    
    online_checks = sum(1 for check in health_checks if check.device_online)
    total_checks = len(health_checks)
    
    return round((online_checks / total_checks) * 100, 2) if total_checks > 0 else 0

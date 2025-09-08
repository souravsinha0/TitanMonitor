from flask_mail import Message
from app import mail
from config import Config
import logging
import requests
import json

class NotificationService:
    def __init__(self):
        self.admin_emails = [email.strip() for email in Config.ADMIN_EMAILS if email.strip()]
    
    def send_alert_notification(self, alert):
        """Send notification for an alert"""
        try:
            # Send email notification
            if self.admin_emails:
                self._send_email_alert(alert)
            
            # Send ServiceNow ticket if configured
            if Config.SERVICENOW_INSTANCE:
                self._create_servicenow_ticket(alert)
            
        except Exception as e:
            logging.error(f"Error sending alert notification: {e}")
    
    def _send_email_alert(self, alert):
        """Send email notification for an alert"""
        try:
            subject = f"[VC Monitoring] {alert.title}"
            
            body = f"""
Alert Details:
Room: {alert.room.name}
Location: {alert.room.location or 'Not specified'}
Alert Type: {alert.alert_type}
Severity: {alert.severity.upper()}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

Description:
{alert.description}

This is an automated notification from the VC Room Monitoring System.
Please investigate and resolve the issue as soon as possible.
            """.strip()
            
            msg = Message(
                subject=subject,
                recipients=self.admin_emails,
                body=body
            )
            
            mail.send(msg)
            logging.info(f"Email alert sent for alert {alert.id}")
            
        except Exception as e:
            logging.error(f"Error sending email alert: {e}")
    
    def _create_servicenow_ticket(self, alert):
        """Create ServiceNow ticket for an alert"""
        try:
            if not all([Config.SERVICENOW_INSTANCE, Config.SERVICENOW_USERNAME, Config.SERVICENOW_PASSWORD]):
                logging.warning("ServiceNow configuration incomplete, skipping ticket creation")
                return
            
            # ServiceNow REST API endpoint
            url = f"https://{Config.SERVICENOW_INSTANCE}.service-now.com/api/now/table/incident"
            
            # Prepare ticket data
            ticket_data = {
                'short_description': alert.title,
                'description': f"""
Room: {alert.room.name}
Location: {alert.room.location or 'Not specified'}
Alert Type: {alert.alert_type}
Severity: {alert.severity}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

{alert.description}

Automatically created by VC Room Monitoring System.
                """.strip(),
                'category': 'Software',
                'subcategory': 'Video Conferencing',
                'urgency': self._map_severity_to_urgency(alert.severity),
                'impact': self._map_severity_to_impact(alert.severity),
                'caller_id': Config.SERVICENOW_USERNAME
            }
            
            # Authentication
            auth = (Config.SERVICENOW_USERNAME, Config.SERVICENOW_PASSWORD)
            
            # Headers
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Make request
            response = requests.post(
                url,
                auth=auth,
                headers=headers,
                data=json.dumps(ticket_data),
                timeout=30
            )
            
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            if 'result' in result:
                ticket_number = result['result'].get('number')
                alert.ticket_id = ticket_number
                
                from app import db
                db.session.commit()
                
                logging.info(f"ServiceNow ticket created: {ticket_number} for alert {alert.id}")
            
        except Exception as e:
            logging.error(f"Error creating ServiceNow ticket: {e}")
    
    def _map_severity_to_urgency(self, severity):
        """Map alert severity to ServiceNow urgency"""
        mapping = {
            'low': '3',
            'medium': '2',
            'high': '1',
            'critical': '1'
        }
        return mapping.get(severity, '3')
    
    def _map_severity_to_impact(self, severity):
        """Map alert severity to ServiceNow impact"""
        mapping = {
            'low': '3',
            'medium': '2',
            'high': '2',
            'critical': '1'
        }
        return mapping.get(severity, '3')
    
    def send_daily_summary(self, summary_data):
        """Send daily summary report"""
        try:
            if not self.admin_emails:
                return
            
            subject = f"Daily VC Monitoring Summary - {summary_data['date']}"
            
            body = f"""
Daily VC Room Monitoring Summary for {summary_data['date']}

Summary:
- Total Rooms: {summary_data['total_rooms']}
- Online Rooms: {summary_data['online_rooms']}
- Offline Rooms: {summary_data['offline_rooms']}
- Health Checks Performed: {summary_data['health_checks_performed']}
- Test Calls Completed: {summary_data['test_calls_completed']}
- New Alerts: {summary_data['new_alerts']}

Room Status:
{self._format_room_status(summary_data['room_status'])}

Recent Alerts:
{self._format_recent_alerts(summary_data['recent_alerts'])}

This is an automated daily summary from the VC Room Monitoring System.
            """.strip()
            
            msg = Message(
                subject=subject,
                recipients=self.admin_emails,
                body=body
            )
            
            mail.send(msg)
            logging.info("Daily summary email sent")
            
        except Exception as e:
            logging.error(f"Error sending daily summary: {e}")
    
    def _format_room_status(self, room_status):
        """Format room status for email"""
        if not room_status:
            return "No room status data available."
        
        lines = []
        for room in room_status:
            lines.append(f"- {room['name']}: {room['status']} (Last check: {room['last_check']})")
        
        return '\n'.join(lines)
    
    def _format_recent_alerts(self, recent_alerts):
        """Format recent alerts for email"""
        if not recent_alerts:
            return "No recent alerts."
        
        lines = []
        for alert in recent_alerts:
            lines.append(f"- [{alert['severity'].upper()}] {alert['title']} ({alert['time']})")
        
        return '\n'.join(lines)

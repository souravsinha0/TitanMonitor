import os

class Config:
    # Cisco Webex API Configuration
    WEBEX_ACCESS_TOKEN = os.environ.get('WEBEX_ACCESS_TOKEN')
    WEBEX_API_BASE_URL = 'https://webexapis.com/v1'
    
    # Default thresholds for call quality
    DEFAULT_PACKET_LOSS_THRESHOLD = 5.0  # percent
    DEFAULT_JITTER_THRESHOLD = 30.0  # milliseconds
    DEFAULT_LATENCY_THRESHOLD = 150.0  # milliseconds
    
    # Health check configuration
    HEALTH_CHECK_TIMEOUT = 30  # seconds
    TEST_CALL_DURATION = 120  # seconds (2 minutes)
    
    # Email notification settings
    ADMIN_EMAILS = os.environ.get('ADMIN_EMAILS', '').split(',')
    
    # ServiceNow integration (optional)
    SERVICENOW_INSTANCE = os.environ.get('SERVICENOW_INSTANCE')
    SERVICENOW_USERNAME = os.environ.get('SERVICENOW_USERNAME')
    SERVICENOW_PASSWORD = os.environ.get('SERVICENOW_PASSWORD')
    
    # Data retention (days)
    HEALTH_CHECK_RETENTION_DAYS = 90
    CALL_DATA_RETENTION_DAYS = 180
    ALERT_RETENTION_DAYS = 365

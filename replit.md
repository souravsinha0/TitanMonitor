# VC Room Monitoring Portal

## Overview

A comprehensive Flask-based web application designed to monitor and manage Cisco Webex video conferencing rooms. The system provides real-time health monitoring, automated test calling, alert management, and detailed reporting capabilities for enterprise video conferencing infrastructure. It integrates with Cisco Webex APIs and RoomOS devices to provide centralized monitoring and proactive maintenance of conference room equipment.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture
- **Framework**: Flask web application with SQLAlchemy ORM for database operations
- **Authentication**: Flask-Login for session management with role-based access control (admin/standard users)
- **Database**: SQLite default with PostgreSQL support via environment configuration
- **Background Processing**: APScheduler for automated health checks, test calls, and data cleanup tasks
- **Email Notifications**: Flask-Mail integration for alert notifications

### Data Models
- **User Management**: User accounts with admin privileges and audit logging
- **Room Management**: Conference room configurations including IP addresses, Cisco Room IDs, and monitoring settings
- **Health Monitoring**: Automated device status checks tracking camera, microphone, speaker functionality
- **Test Calling**: Scheduled quality assessment calls with metrics collection
- **Alert System**: Multi-severity alert management with notification workflows

### API Integration Layer
- **Webex API Service**: Integration with Cisco Webex cloud APIs for device management and call analytics
- **RoomOS API Service**: Direct communication with on-premise RoomOS devices for detailed hardware status
- **ServiceNow Integration**: Optional ticketing system integration for automated incident creation

### Monitoring and Scheduling
- **Health Check Scheduler**: Daily automated device status verification
- **Test Call Scheduler**: Configurable per-room test calling with quality metrics
- **Data Retention**: Automated cleanup of historical data based on configured retention policies
- **Real-time Status**: Live device status monitoring with threshold-based alerting

### Frontend Architecture
- **Template Engine**: Jinja2 templating with Bootstrap 5 dark theme
- **Interactive Elements**: Chart.js for analytics visualization and DataTables for data management
- **Responsive Design**: Mobile-friendly interface with FontAwesome icons
- **Role-based UI**: Administrative functions hidden from standard users

## External Dependencies

### Third-party Services
- **Cisco Webex APIs**: Cloud-based device management and call analytics
- **ServiceNow REST API**: Optional incident management integration
- **SMTP Email Service**: Gmail or custom SMTP server for alert notifications

### JavaScript Libraries
- **Bootstrap 5**: UI framework with Replit dark theme
- **Chart.js**: Data visualization for monitoring dashboards
- **DataTables**: Enhanced table functionality with sorting and filtering
- **FontAwesome**: Icon library for UI elements

### Python Packages
- **Flask Ecosystem**: Core web framework with SQLAlchemy, Login, and Mail extensions
- **APScheduler**: Background task scheduling for monitoring operations
- **Requests**: HTTP client for external API communications
- **Werkzeug**: Security utilities for password hashing and proxy handling

### Database Options
- **SQLite**: Default embedded database for development and small deployments
- **PostgreSQL**: Production database option via DATABASE_URL environment variable
- **Connection Pooling**: Configured with automatic reconnection and connection recycling
import requests
import base64
import logging
from requests.auth import HTTPBasicAuth
from config import Config

class RoomOSAPI:
    def __init__(self, room_ip, username='admin', password=''):
        self.room_ip = room_ip
        self.username = username
        self.password = password
        self.base_url = f"https://{room_ip}"
        self.timeout = Config.HEALTH_CHECK_TIMEOUT
    
    def get_device_status(self):
        """Get comprehensive device status from RoomOS device"""
        try:
            # Disable SSL warnings for self-signed certificates
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            status_data = {}
            
            # Get system unit information
            system_info = self._get_system_info()
            if system_info['success']:
                status_data.update(system_info['data'])
            
            # Get peripheral status
            peripheral_status = self._get_peripheral_status()
            if peripheral_status['success']:
                status_data.update(peripheral_status['data'])
            
            # Get network information
            network_info = self._get_network_info()
            if network_info['success']:
                status_data.update(network_info['data'])
            
            # Get diagnostics
            diagnostics = self._get_diagnostics()
            if diagnostics['success']:
                status_data.update(diagnostics['data'])
            
            return {
                'success': True,
                'data': status_data
            }
            
        except Exception as e:
            logging.error(f"Error getting device status from {self.room_ip}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _make_request(self, endpoint, method='GET', data=None):
        """Make authenticated request to RoomOS device"""
        try:
            url = f"{self.base_url}/xmlapi/{endpoint}"
            
            auth = HTTPBasicAuth(self.username, self.password)
            
            if method == 'GET':
                response = requests.get(url, auth=auth, verify=False, timeout=self.timeout)
            elif method == 'POST':
                response = requests.post(url, auth=auth, data=data, verify=False, timeout=self.timeout)
            
            response.raise_for_status()
            return {
                'success': True,
                'content': response.text,
                'status_code': response.status_code
            }
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed for {endpoint}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_system_info(self):
        """Get system information"""
        try:
            # Get system unit status
            result = self._make_request('status.xml?location=/Status/SystemUnit')
            
            if not result['success']:
                return result
            
            # Parse XML response (simplified - in production would use proper XML parser)
            content = result['content']
            
            # Extract key information using basic string parsing
            # In production, use xml.etree.ElementTree or similar
            data = {
                'device_online': True,  # If we got a response, device is online
                'software_version': self._extract_xml_value(content, 'Software/Version'),
                'uptime_hours': self._extract_uptime(content),
                'temperature': self._extract_xml_value(content, 'Temperature', float)
            }
            
            return {
                'success': True,
                'data': data
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_peripheral_status(self):
        """Get peripheral device status"""
        try:
            result = self._make_request('status.xml?location=/Status/Peripherals')
            
            if not result['success']:
                return result
            
            content = result['content']
            
            data = {
                'camera_status': self._extract_camera_status(content),
                'microphone_status': self._extract_microphone_status(content),
                'speaker_status': self._extract_speaker_status(content)
            }
            
            return {
                'success': True,
                'data': data
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_network_info(self):
        """Get network information"""
        try:
            result = self._make_request('status.xml?location=/Status/Network')
            
            if not result['success']:
                return result
            
            content = result['content']
            
            data = {
                'network_status': 'connected' if 'Connected' in content else 'disconnected',
                'ip_address': self._extract_xml_value(content, 'IPv4/Address')
            }
            
            return {
                'success': True,
                'data': data
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_diagnostics(self):
        """Get diagnostic information"""
        try:
            result = self._make_request('status.xml?location=/Status/Diagnostics')
            
            if not result['success']:
                return result
            
            content = result['content']
            
            data = {
                'diagnostics_status': 'pass' if 'OK' in content else 'warning'
            }
            
            return {
                'success': True,
                'data': data
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _extract_xml_value(self, content, tag_path, value_type=str):
        """Extract value from XML content using tag path"""
        try:
            # Simple XML parsing - in production use proper XML parser
            import re
            
            # Build regex pattern for nested tags
            tags = tag_path.split('/')
            pattern = ''
            for tag in tags:
                pattern += f'<{tag}[^>]*>(.*?)</{tag}>'
            
            match = re.search(pattern, content, re.DOTALL)
            if match:
                value = match.group(1).strip()
                if value_type == float:
                    return float(value) if value.replace('.', '').isdigit() else None
                elif value_type == int:
                    return int(value) if value.isdigit() else None
                else:
                    return value
            return None
            
        except Exception as e:
            logging.error(f"Error extracting XML value {tag_path}: {e}")
            return None
    
    def _extract_uptime(self, content):
        """Extract uptime and convert to hours"""
        try:
            uptime_str = self._extract_xml_value(content, 'Uptime')
            if uptime_str:
                # Convert uptime format to hours (simplified)
                # Format might be like "P2DT3H45M30S" (ISO 8601 duration)
                import re
                
                days_match = re.search(r'(\d+)D', uptime_str)
                hours_match = re.search(r'(\d+)H', uptime_str)
                
                days = int(days_match.group(1)) if days_match else 0
                hours = int(hours_match.group(1)) if hours_match else 0
                
                return (days * 24) + hours
            return None
            
        except Exception as e:
            logging.error(f"Error extracting uptime: {e}")
            return None
    
    def _extract_camera_status(self, content):
        """Extract camera status from peripheral content"""
        try:
            if 'Camera' in content:
                if 'Connected' in content or 'OK' in content:
                    return 'connected'
                else:
                    return 'disconnected'
            return 'unknown'
        except:
            return 'unknown'
    
    def _extract_microphone_status(self, content):
        """Extract microphone status from peripheral content"""
        try:
            if 'Microphone' in content:
                if 'Connected' in content or 'OK' in content:
                    return 'connected'
                else:
                    return 'disconnected'
            return 'unknown'
        except:
            return 'unknown'
    
    def _extract_speaker_status(self, content):
        """Extract speaker status from peripheral content"""
        try:
            if 'Speaker' in content:
                if 'Connected' in content or 'OK' in content:
                    return 'connected'
                else:
                    return 'disconnected'
            return 'unknown'
        except:
            return 'unknown'
    
    def start_test_call(self, meeting_url):
        """Start a test call to the specified meeting URL"""
        try:
            # Use RoomOS command to join meeting
            command_data = f'''<Command>
                <Dial>
                    <Number>{meeting_url}</Number>
                </Dial>
            </Command>'''
            
            result = self._make_request('command/Dial', method='POST', data=command_data)
            
            if result['success']:
                return {
                    'success': True,
                    'call_id': self._extract_call_id(result['content'])
                }
            else:
                return result
                
        except Exception as e:
            logging.error(f"Error starting test call: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def end_call(self, call_id=None):
        """End active call"""
        try:
            command_data = '<Command><Call><Disconnect/></Call></Command>'
            
            result = self._make_request('command/Call/Disconnect', method='POST', data=command_data)
            
            return result
            
        except Exception as e:
            logging.error(f"Error ending call: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _extract_call_id(self, content):
        """Extract call ID from response"""
        try:
            call_id = self._extract_xml_value(content, 'CallId')
            return call_id
        except:
            return None

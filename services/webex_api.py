import requests
import logging
from datetime import datetime, timedelta
from config import Config

class WebexAPI:
    def __init__(self):
        self.base_url = Config.WEBEX_API_BASE_URL
        self.access_token = Config.WEBEX_ACCESS_TOKEN
        self.headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    def get_room_devices(self):
        """Get list of all room devices"""
        try:
            url = f"{self.base_url}/devices"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return {
                'success': True,
                'devices': data.get('items', [])
            }
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching room devices: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_device_status(self, device_id):
        """Get status of a specific device"""
        try:
            url = f"{self.base_url}/devices/{device_id}"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            device_data = response.json()
            
            # Get additional device details
            url_status = f"{self.base_url}/devices/{device_id}/status"
            response_status = requests.get(url_status, headers=self.headers, timeout=30)
            
            status_data = {}
            if response_status.status_code == 200:
                status_data = response_status.json()
            
            return {
                'success': True,
                'device': device_data,
                'status': status_data
            }
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching device status for {device_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_meeting(self, title, start_time, duration_minutes=2):
        """Create a meeting for test call"""
        try:
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            meeting_data = {
                'title': title,
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'timezone': 'UTC',
                'allowAnyUserToBeCoHost': True,
                'enabledAutoRecordMeeting': False,
                'allowFirstUserToBeCoHost': True,
                'meetingType': 'meetingSeries'
            }
            
            url = f"{self.base_url}/meetings"
            response = requests.post(url, json=meeting_data, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            meeting = response.json()
            return {
                'success': True,
                'meeting': meeting
            }
        except requests.exceptions.RequestException as e:
            logging.error(f"Error creating meeting: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_meeting(self, meeting_id):
        """Delete a meeting"""
        try:
            url = f"{self.base_url}/meetings/{meeting_id}"
            response = requests.delete(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            return {
                'success': True
            }
        except requests.exceptions.RequestException as e:
            logging.error(f"Error deleting meeting {meeting_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_meeting_quality(self, meeting_id):
        """Get quality metrics for a completed meeting"""
        try:
            # Get meeting participants
            url = f"{self.base_url}/meetings/{meeting_id}/participants"
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': 'Meeting not found or no participants'
                }
            
            participants = response.json().get('items', [])
            
            # For each participant, try to get quality metrics
            quality_metrics = []
            for participant in participants:
                participant_id = participant.get('id')
                if participant_id:
                    quality_url = f"{self.base_url}/meetings/{meeting_id}/participants/{participant_id}/quality"
                    quality_response = requests.get(quality_url, headers=self.headers, timeout=30)
                    
                    if quality_response.status_code == 200:
                        quality_data = quality_response.json()
                        quality_metrics.append(quality_data)
            
            # Calculate average metrics
            if quality_metrics:
                avg_metrics = self._calculate_average_quality(quality_metrics)
                return {
                    'success': True,
                    'quality_metrics': avg_metrics
                }
            else:
                return {
                    'success': False,
                    'error': 'No quality metrics available'
                }
                
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching meeting quality for {meeting_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_average_quality(self, quality_metrics):
        """Calculate average quality metrics from participant data"""
        total_participants = len(quality_metrics)
        
        if total_participants == 0:
            return {}
        
        # Initialize totals
        total_packet_loss = 0
        total_jitter = 0
        total_latency = 0
        
        for metrics in quality_metrics:
            # Extract metrics (structure may vary based on actual API response)
            audio_metrics = metrics.get('audio', {})
            video_metrics = metrics.get('video', {})
            
            # Audio metrics
            total_packet_loss += audio_metrics.get('packetLossPercent', 0)
            total_jitter += audio_metrics.get('jitter', 0)
            total_latency += audio_metrics.get('latency', 0)
            
            # Video metrics (if different from audio)
            video_packet_loss = video_metrics.get('packetLossPercent', 0)
            video_jitter = video_metrics.get('jitter', 0)
            video_latency = video_metrics.get('latency', 0)
            
            if video_packet_loss > total_packet_loss / total_participants:
                total_packet_loss += video_packet_loss
            if video_jitter > total_jitter / total_participants:
                total_jitter += video_jitter
            if video_latency > total_latency / total_participants:
                total_latency += video_latency
        
        # Calculate averages
        avg_metrics = {
            'packet_loss_percent': round(total_packet_loss / total_participants, 2),
            'jitter_ms': round(total_jitter / total_participants, 2),
            'latency_ms': round(total_latency / total_participants, 2),
            'call_quality_score': self._calculate_quality_score(
                total_packet_loss / total_participants,
                total_jitter / total_participants,
                total_latency / total_participants
            )
        }
        
        return avg_metrics
    
    def _calculate_quality_score(self, packet_loss, jitter, latency):
        """Calculate overall call quality score (1-10)"""
        # Simple scoring algorithm - can be improved
        score = 10.0
        
        # Deduct points for packet loss
        if packet_loss > 5:
            score -= 3
        elif packet_loss > 2:
            score -= 1
        elif packet_loss > 1:
            score -= 0.5
        
        # Deduct points for jitter
        if jitter > 50:
            score -= 2
        elif jitter > 30:
            score -= 1
        elif jitter > 20:
            score -= 0.5
        
        # Deduct points for latency
        if latency > 200:
            score -= 2
        elif latency > 150:
            score -= 1
        elif latency > 100:
            score -= 0.5
        
        return max(1.0, round(score, 1))

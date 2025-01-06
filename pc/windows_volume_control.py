import serial
import json
import time
import psutil
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import serial.tools.list_ports
import logging

# Set up logging to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class VolumeController:
    def __init__(self):
        self.com_port = None
        self.serial = None
        self.connected = False
        self.last_app_list = []
        self.update_interval = 1.0  # How often to update app list (seconds)
        self.last_update = 0
        
        # Initialize system audio endpoint
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        self.system_volume = cast(interface, POINTER(IAudioEndpointVolume))
    
    def find_pico_com_port(self):
        """Find the COM port for the Pico device"""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # Look for Raspberry Pi Pico vendor ID (0x2E8A)
            if "2E8A" in port.hwid:
                self.com_port = port.device
                logging.info(f"Found Pico on {self.com_port}")
                return True
        logging.error("Could not find Pico device")
        return False
    
    def connect(self):
        """Establish connection to the Pico"""
        if not self.com_port and not self.find_pico_com_port():
            return False
            
        try:
            logging.info(f"Attempting to connect to {self.com_port}")
            self.serial = serial.Serial(self.com_port, 115200, timeout=1)
            self.connected = True
            logging.info("Serial connection established")
            
            # Wait for initial communication
            logging.info("Waiting for initial communication from Pico...")
            time.sleep(0.5)
            
            # Check for any initial data
            if self.serial.in_waiting:
                try:
                    line = self.serial.readline().decode('utf-8').strip()
                    logging.info(f"Initial data received: {line}")
                    if line:
                        try:
                            data = json.loads(line)
                            if data.get("type") == "test":
                                logging.info("Received test message, sending response")
                                response = {"type": "test_response", "status": "ok"}
                                if self.send_response(response):
                                    logging.info("Test response sent successfully")
                                else:
                                    logging.error("Failed to send test response")
                        except json.JSONDecodeError:
                            logging.warning("Initial data was not JSON")
                except Exception as e:
                    logging.error(f"Error processing initial data: {e}")
            
            logging.info("Successfully connected to Pico")
            return True
            
        except serial.SerialException as e:
            logging.error(f"Serial connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Safely disconnect from the Pico"""
        if self.serial:
            self.serial.close()
        self.connected = False
        logging.info("Disconnected from Pico")
    
    def get_application_volumes(self):
        """Get list of applications and their volumes"""
        sessions = AudioUtilities.GetAllSessions()
        app_volumes = []
        
        for session in sessions:
            try:
                if session.Process and session.Process.name():
                    volume = session.SimpleAudioVolume.GetMasterVolume()
                    muted = session.SimpleAudioVolume.GetMute()
                    app_volumes.append({
                        "name": session.Process.name(),
                        "volume": int(volume * 100),
                        "muted": muted
                    })
            except Exception as e:
                logging.warning(f"Error getting volume for session: {e}")
        
        self.last_app_list = app_volumes
        return app_volumes
    
    def set_application_volume(self, app_name, volume):
        """Set volume for a specific application"""
        sessions = AudioUtilities.GetAllSessions()
        
        for session in sessions:
            try:
                if session.Process and session.Process.name() == app_name:
                    volume_interface = session.SimpleAudioVolume
                    volume_interface.SetMasterVolume(volume / 100, None)
                    logging.info(f"Set {app_name} volume to {volume}")
                    return True
            except Exception as e:
                logging.error(f"Error setting volume for {app_name}: {e}")
        
        return False
    
    def set_system_volume(self, volume):
        """Set system master volume"""
        try:
            self.system_volume.SetMasterVolumeLevelScalar(volume / 100, None)
            logging.info(f"Set system volume to {volume}")
            return True
        except Exception as e:
            logging.error(f"Error setting system volume: {e}")
            return False
    
    def toggle_mute(self, app_name=None):
        """Toggle mute for system or specific app"""
        try:
            if app_name:
                sessions = AudioUtilities.GetAllSessions()
                for session in sessions:
                    if session.Process and session.Process.name() == app_name:
                        volume_interface = session.SimpleAudioVolume
                        current_mute = volume_interface.GetMute()
                        volume_interface.SetMute(not current_mute, None)
                        logging.info(f"Toggled mute for {app_name}")
                        return True
            else:
                current_mute = self.system_volume.GetMute()
                self.system_volume.SetMute(not current_mute, None)
                logging.info("Toggled system mute")
                return True
        except Exception as e:
            logging.error(f"Error toggling mute: {e}")
            return False
    
    def handle_message(self, data):
        """Handle incoming messages from Pico"""
        try:
            if data["type"] == "test":
                # Respond to test message to confirm connection
                logging.info("Received test message from Pico")
                response = {
                    "type": "test_response",
                    "status": "ok"
                }
                if self.send_response(response):
                    logging.info("Sent test response to Pico")
                else:
                    logging.error("Failed to send test response")
                return
                
            elif data["type"] == "request_apps":
                app_volumes = self.get_application_volumes()
                response = {
                    "type": "apps",
                    "data": app_volumes
                }
                self.send_response(response)
                
            elif data["type"] == "set_volume":
                if data["app"] == "System":
                    success = self.set_system_volume(data["volume"])
                else:
                    success = self.set_application_volume(data["app"], data["volume"])
                response = {
                    "type": "volume_set",
                    "success": success,
                    "app": data["app"]
                }
                self.send_response(response)
                
            elif data["type"] == "toggle_mute":
                success = self.toggle_mute(data.get("app"))  # None for system mute
                response = {
                    "type": "mute_toggled",
                    "success": success,
                    "app": data.get("app", "System")
                }
                self.send_response(response)
                
        except Exception as e:
            logging.error(f"Error handling message: {e}")
            self.send_response({"type": "error", "message": str(e)})
    
    def send_response(self, data):
        """Send response to Pico"""
        if not self.connected:
            return False
            
        try:
            self.serial.write((json.dumps(data) + '\n').encode('utf-8'))
            return True
        except Exception as e:
            logging.error(f"Error sending response: {e}")
            return False
    
    def run(self):
        """Main run loop"""
        logging.info("Starting volume control service")
        
        while True:
            # If not connected, try to connect
            if not self.connected:
                if self.find_pico_com_port():
                    if self.connect():
                        logging.info("Successfully connected to Pico")
                    else:
                        logging.error("Failed to connect to Pico")
                        time.sleep(1)  # Wait before retry
                else:
                    logging.info("Waiting for Pico to be connected...")
                    time.sleep(1)  # Don't spam port detection
                continue
            
            try:
                # Check for incoming messages
                if self.serial.in_waiting:
                    try:
                        line = self.serial.readline().decode('utf-8').strip()
                        logging.info(f"Received raw data: {line}")  # Log raw data
                        if line:
                            data = json.loads(line)
                            logging.info(f"Parsed JSON: {data}")  # Log parsed JSON
                            self.handle_message(data)
                    except json.JSONDecodeError as je:
                        logging.warning(f"Invalid JSON received: {line} - Error: {je}")
                    except Exception as e:
                        logging.error(f"Error processing message: {e}")
                
                # Periodically update app list
                current_time = time.time()
                if current_time - self.last_update >= self.update_interval:
                    app_volumes = self.get_application_volumes()
                    if app_volumes != self.last_app_list:
                        response = {
                            "type": "apps_update",
                            "data": app_volumes
                        }
                        self.send_response(response)
                    self.last_update = current_time
                
                time.sleep(0.1)  # Prevent CPU hogging
                
            except serial.SerialException as e:
                logging.error(f"Serial connection lost: {e}")
                self.disconnect()  # Clean up the connection
                continue  # Go back to connection attempt
                
            except Exception as e:
                logging.error(f"Service error: {e}")
                # Don't disconnect on non-serial errors
                
        logging.info("Service stopped")

def main():
    controller = VolumeController()
    controller.run()

if __name__ == "__main__":
    main() 
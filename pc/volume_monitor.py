import serial
import json
import time
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
import serial.tools.list_ports
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('volume_monitor.log')
    ]
)

class VolumeMonitor:
    def __init__(self):
        self.com_port = None
        self.serial = None
        self.connected = False
        self.last_app_list = {}
        self.update_interval = 2.0
        self.last_update = 0
        
    def find_pico_com_port(self):
        """Find the COM port for the Pico device"""
        # Force using COM8
        self.com_port = "COM7"
        logging.info(f"Using Pico CDC on {self.com_port}")
        return True
        
    def connect(self):
        """Connect to Pico and perform handshake"""
        # Close any existing connection
        if self.serial:
            try:
                self.serial.close()
            except:
                pass
            self.serial = None
            time.sleep(0.1)  # Wait before reconnecting
            
        try:
            if not self.com_port and not self.find_pico_com_port():
                return False
                
            # Try to open the port (no baud rate needed for CDC)
            try:
                self.serial = serial.Serial(
                    port=self.com_port,
                    timeout=1,
                    write_timeout=1
                )
            except serial.SerialException as e:
                if "Access is denied" in str(e):
                    logging.error(f"Port access denied on {self.com_port} - waiting before retry")
                    time.sleep(2)
                    return False
                raise
                
            logging.info("Serial port opened, attempting handshake...")
            
            # Clear any pending data
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # Send test message
            self.send_message({"type": "test"})
            
            # Wait for response
            start_time = time.time()
            while time.time() - start_time < 5:  # 5 second timeout
                if self.serial.in_waiting:
                    try:
                        line = self.serial.readline().decode().strip()
                        if line:
                            logging.debug(f"Received: {line}")
                            data = json.loads(line)
                            if data.get("type") in ["test_response", "ready"]:
                                logging.info("Test response received")
                                # Send connected message
                                self.send_message({"type": "connected"})
                                self.connected = True
                                return True
                    except Exception as e:
                        logging.debug(f"Error processing response: {e}")
                time.sleep(0.1)
                
            logging.error("No response to test message")
            self.disconnect()
            return False
            
        except Exception as e:
            logging.error(f"Connection failed: {e}")
            self.disconnect()
            return False
            
    def disconnect(self):
        """Safely disconnect from the device"""
        self.connected = False
        if self.serial:
            try:
                self.serial.close()
            except:
                pass
            self.serial = None
            time.sleep(0.1)
            
    def send_message(self, data):
        """Send message to Pico"""
        if not self.serial:
            return False
            
        try:
            message = json.dumps(data) + '\n'
            self.serial.write(message.encode())
            self.serial.flush()  # Ensure data is sent
            logging.info(f"Sent: {message.strip()}")
            return True
        except Exception as e:
            logging.error(f"Failed to send message: {e}")
            self.disconnect()
            return False
            
    def get_application_volumes(self):
        """Get list of applications and their volumes"""
        sessions = AudioUtilities.GetAllSessions()
        app_volumes = []
        
        for session in sessions:
            try:
                if session.Process and session.Process.name():
                    volume = session.SimpleAudioVolume
                    app_volumes.append({
                        "name": session.Process.name(),
                        "volume": int(volume.GetMasterVolume() * 100),
                        "muted": volume.GetMute()
                    })
            except:
                continue
                
        return app_volumes
        
    def handle_message(self, data):
        """Handle incoming messages from Pico"""
        try:
            msg_type = data.get("type", "")
            logging.debug(f"Processing message type: {msg_type}")
            
            if msg_type == "request_apps":
                app_volumes = self.get_application_volumes()
                self.send_message({
                    "type": "apps_update",
                    "data": app_volumes
                })
                
        except Exception as e:
            logging.error(f"Error handling message: {e}")
            
    def update(self):
        """Main update loop"""
        if not self.connected:
            if not self.connect():
                time.sleep(1)  # Wait before retry
                return
                
        try:
            # Check for incoming messages
            if self.serial and self.serial.in_waiting:
                try:
                    line = self.serial.readline().decode().strip()
                    if line:
                        data = json.loads(line)
                        self.handle_message(data)
                except Exception as e:
                    logging.error(f"Error reading message: {e}")
                    self.disconnect()
                    
            # Periodically update app list
            current_time = time.time()
            if current_time - self.last_update >= self.update_interval:
                app_volumes = self.get_application_volumes()
                if app_volumes != self.last_app_list:
                    self.send_message({
                        "type": "apps_update",
                        "data": app_volumes
                    })
                    self.last_app_list = app_volumes
                self.last_update = current_time
                
            time.sleep(0.01)  # Small delay
            
        except Exception as e:
            logging.error(f"Update error: {e}")
            self.disconnect()

def main():
    monitor = VolumeMonitor()
    logging.info("Volume Monitor starting...")
    
    try:
        while True:
            try:
                monitor.update()
            except KeyboardInterrupt:
                logging.info("Shutting down...")
                monitor.disconnect()
                break
            except Exception as e:
                logging.error(f"Main loop error: {e}")
                time.sleep(1)
    finally:
        monitor.disconnect()
        logging.info("Volume Monitor stopped")

if __name__ == "__main__":
    main() 
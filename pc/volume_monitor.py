from icon_handler import IconHandler
import serial
import json
import time
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
import serial.tools.list_ports
import logging
import sys
import base64

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
        self.initialized = False  # Track if initial config is done
        self.last_app_list = {}
        self.update_interval = 1.0  # Check more frequently but only send on changes
        self.last_update = 0
        self.icon_handler = IconHandler()
        self.last_icon_send = 0
        self.icon_send_timeout = 1.0
        self.sent_icons = set()
        
    def find_pico_com_port(self):
        """Find the COM port for the Pico device"""
        # Force using COM8
        self.com_port = "COM7"
        logging.info(f"Using Pico CDC on {self.com_port}")
        return True
        
    def connect(self):
        """Connect to Pico and perform handshake"""
        if not self.find_pico_com_port():
            return False
            
        try:
            # Open serial port
            self.serial = serial.Serial(
                port=self.com_port,
                timeout=1,
                write_timeout=1
            )
            logging.info("Serial port opened, attempting handshake...")
            
            # Clear any pending data
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # Send test message and wait for response
            self.send_message({"type": "test"})
            
            start_time = time.time()
            while time.time() - start_time < 5:  # 5 second timeout
                if self.serial.in_waiting:
                    try:
                        line = self.serial.readline().decode().strip()
                        if line:
                            data = json.loads(line)
                            if data.get("type") == "test_response":
                                logging.info("Test response received")
                                # Send connected message
                                self.send_message({"type": "connected"})
                                self.connected = True
                                # Start initialization sequence
                                return self.initialize_connection()
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
            
    def initialize_connection(self):
        """Send initial configuration to Pico"""
        try:
            # Get initial app list and icons
            app_volumes, icons = self.get_application_volumes()
            
            # Send initial app list
            success = self.send_message({
                "type": "initial_config",
                "data": app_volumes
            })
            if not success:
                return False
                
            time.sleep(0.5)
            
            # Send icons one by one
            for icon_data in icons:
                if not icon_data.get("icon"):
                    continue
                    
                success = self.send_message({
                    "type": "icon_data",
                    "app": icon_data["name"]
                }, icon_data["icon"])
                
                if success:
                    self.sent_icons.add(icon_data["name"])
                else:
                    logging.error(f"Failed to send icon for {icon_data['name']}")
                    return False
                    
                time.sleep(0.5)
            
            # Send initialization complete message
            success = self.send_message({
                "type": "init_complete"
            })
            
            if success:
                # Wait for ready confirmation from Pico
                start_time = time.time()
                while time.time() - start_time < 5:  # 5 second timeout
                    if self.serial.in_waiting:
                        try:
                            line = self.serial.readline().decode().strip()
                            if line:
                                data = json.loads(line)
                                if data.get("type") == "ready":
                                    logging.info("Pico ready for updates")
                                    self.initialized = True
                                    self.last_app_list = {app["name"]: app for app in app_volumes}
                                    return True
                        except Exception as e:
                            logging.debug(f"Error processing response: {e}")
                    time.sleep(0.1)
                    
            logging.error("Initialization failed")
            return False
            
        except Exception as e:
            logging.error(f"Initialization failed: {e}")
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
        # Clear icon cache and sent icons tracking on disconnect
        self.icon_handler.clear_cache()
        self.sent_icons.clear()
            
    def send_message(self, data, icon_data=None):
        """Send message to Pico"""
        if not self.serial:
            return False
            
        try:
            # Send the JSON message
            message = json.dumps(data) + '\n'
            self.serial.write(message.encode())
            self.serial.flush()
            
            if icon_data:
                current_time = time.time()
                if current_time - self.last_icon_send < self.icon_send_timeout:
                    time.sleep(self.icon_send_timeout - (current_time - self.last_icon_send))
                
                # Log the message and icon data size
                logging.info(f"Sent message before icon: {message.strip()}")
                logging.info(f"Icon data size for {data.get('app', 'unknown')}: {len(icon_data)} bytes")
                
                # Wait for message to be processed
                time.sleep(0.5)
                
                # Send icon data with markers
                self.serial.write(b'<ICON_START>')
                self.serial.flush()
                
                # Ensure icon_data is bytes
                if isinstance(icon_data, str):
                    icon_data = icon_data.encode('utf-8')
                elif not isinstance(icon_data, bytes):
                    icon_data = str(icon_data).encode('utf-8')
                
                # Send icon data in smaller chunks with longer delays
                chunk_size = 64
                for i in range(0, len(icon_data), chunk_size):
                    chunk = icon_data[i:i + chunk_size]
                    self.serial.write(chunk)
                    self.serial.flush()
                    time.sleep(0.1)
                
                self.serial.write(b'<ICON_END>')
                self.serial.flush()
                logging.info(f"Finished sending icon data for: {data.get('app', 'unknown')}")
                self.last_icon_send = time.time()
                time.sleep(0.5)
            else:
                logging.info(f"Sent: {message.strip()}")
                time.sleep(0.1)
            
            return True
        except Exception as e:
            logging.error(f"Failed to send message: {e}")
            self.disconnect()
            return False
            
    def get_application_volumes(self):
        """Get list of applications and their volumes"""
        sessions = AudioUtilities.GetAllSessions()
        app_volumes = []
        icons_to_send = []
        
        for session in sessions:
            try:
                if session.Process and session.Process.name():
                    volume = session.SimpleAudioVolume
                    process_name = session.Process.name()
                    pid = session.Process.pid
                    
                    # Get icon data
                    icon_data = self.icon_handler.get_icon_for_app(process_name, pid)
                    
                    # Add basic app info
                    app_volumes.append({
                        "name": process_name,
                        "volume": int(volume.GetMasterVolume() * 100),
                        "muted": volume.GetMute(),
                        "has_icon": icon_data is not None
                    })
                    
                    # Queue icon for separate transmission
                    if icon_data:
                        icons_to_send.append({
                            "name": process_name,
                            "icon": icon_data
                        })
                        
            except:
                continue
                
        return app_volumes, icons_to_send
        
    def handle_message(self, data):
        """Handle incoming messages from Pico"""
        try:
            msg_type = data.get("type", "")
            logging.debug(f"Processing message type: {msg_type}")
            
            if msg_type == "request_apps":
                app_volumes, icons = self.get_application_volumes()
                
                # Send app info first and wait for it to be processed
                self.send_message({
                    "type": "apps_update",
                    "data": app_volumes
                })
                time.sleep(0.5)
                
                # Then send each icon separately with proper framing
                for icon_data in icons:
                    if not icon_data.get("icon"):  # Skip if no icon data
                        continue
                        
                    # Skip if we've already sent this icon
                    if icon_data["name"] in self.sent_icons:
                        continue
                        
                    success = self.send_message({
                        "type": "icon_data",
                        "app": icon_data["name"]
                    }, icon_data["icon"])
                    
                    if success:
                        self.sent_icons.add(icon_data["name"])
                    else:
                        logging.error(f"Failed to send icon for {icon_data['name']}")
                        break
                    
                    time.sleep(0.5)
                    
        except Exception as e:
            logging.error(f"Error handling message: {e}")
            
    def update(self):
        """Main update loop"""
        if not self.connected or not self.initialized:
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
                except json.JSONDecodeError as e:
                    logging.error(f"Invalid JSON: {e}")
                except Exception as e:
                    logging.error(f"Error reading message: {e}")
                    self.disconnect()
                    
            # Check for app changes
            current_time = time.time()
            if current_time - self.last_update >= self.update_interval:
                app_volumes, icons = self.get_application_volumes()
                
                # Convert to dict for easier comparison
                current_apps = {app["name"]: app for app in app_volumes}
                
                # Check for changes
                changes = {
                    "added": [],
                    "removed": [],
                    "updated": []
                }
                
                # Find added and updated apps
                for name, app in current_apps.items():
                    if name not in self.last_app_list:
                        changes["added"].append(app)
                    elif (app["volume"] != self.last_app_list[name]["volume"] or 
                          app["muted"] != self.last_app_list[name]["muted"]):
                        changes["updated"].append(app)
                
                # Find removed apps
                for name in self.last_app_list:
                    if name not in current_apps:
                        changes["removed"].append(name)
                
                # Send updates if there are any changes
                if changes["added"] or changes["removed"] or changes["updated"]:
                    # Send app changes
                    self.send_message({
                        "type": "app_changes",
                        "added": changes["added"],
                        "removed": changes["removed"],
                        "updated": changes["updated"]
                    })
                    
                    # Send icons for new apps
                    for app in changes["added"]:
                        icon_data = next((icon for icon in icons if icon["name"] == app["name"] and icon.get("icon")), None)
                        if icon_data and app["name"] not in self.sent_icons:
                            success = self.send_message({
                                "type": "icon_data",
                                "app": app["name"]
                            }, icon_data["icon"])
                            
                            if success:
                                self.sent_icons.add(app["name"])
                            else:
                                logging.error(f"Failed to send icon for {app['name']}")
                                break
                                
                            time.sleep(0.5)
                    
                    # Update last app list
                    self.last_app_list = current_apps
                    
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
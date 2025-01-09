from icon_handler import IconHandler
import serial
import json
import time
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
import serial.tools.list_ports
import sys

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
        # List all COM ports
        ports = list(serial.tools.list_ports.comports())
        pico_ports = []
        
        for port in ports:
            if "Board in FS mode" in port.description:
                pico_ports.append(port.device)
                print(f"Found Pico CDC on {port.device}")
        
        if pico_ports:
            # Try each found port
            for port in pico_ports:
                self.com_port = port
                if self.try_connect():
                    return True
            
        # If not found or none worked, try COM7 as fallback
        self.com_port = "COM7"
        print(f"Using fallback Pico CDC on {self.com_port}")
        return self.try_connect()
        
    def try_connect(self):
        """Try to connect to a specific COM port"""
        try:
            # Close any existing connection
            if self.serial and self.serial.is_open:
                self.serial.close()
                time.sleep(1)
            
            # Simple serial connection like Thonny uses
            self.serial = serial.Serial(
                port=self.com_port,
                baudrate=115200,
                timeout=1
            )
            
            print("Port opened, testing communication...")
            
            # Give a moment for the connection to stabilize
            time.sleep(0.5)
            
            # Try to send test message
            if self.send_message({"type": "test"}):
                print("Waiting for response...")
                # Wait for response
                start_time = time.time()
                while time.time() - start_time < 5:  # 5 second timeout
                    if self.serial.in_waiting:
                        try:
                            line = self.serial.readline().decode().strip()
                            if line:
                                print(f"Received: {line}")
                                data = json.loads(line)
                                if data.get("type") == "test_response" and data.get("status") == "ok":
                                    print("Successfully connected")
                                    return True
                        except Exception as e:
                            print(f"Error processing response: {e}")
                    time.sleep(0.1)
            
            print("No response received")
            self.disconnect()
            return False
            
        except Exception as e:
            print(f"Connection attempt failed: {e}")
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
        # Clear icon cache and sent icons tracking on disconnect
        self.icon_handler.clear_cache()
        self.sent_icons.clear()
            
    def send_message(self, data, icon_data=None):
        """Send message to Pico"""
        if not self.serial:
            return False
            
        try:
            # Send the JSON message in chunks
            message = json.dumps(data) + '\n'
            bytes_to_write = message.encode()
            chunk_size = 32  # Match Pico's chunk size
            
            for i in range(0, len(bytes_to_write), chunk_size):
                chunk = bytes_to_write[i:i + chunk_size]
                retries = 3
                while retries > 0:
                    try:
                        bytes_written = self.serial.write(chunk)
                        if bytes_written > 0:
                            break
                        retries -= 1
                        time.sleep(0.01)
                    except Exception as e:
                        retries -= 1
                        time.sleep(0.01)
                        if retries == 0:
                            print(f"Failed to send chunk after retries: {str(e)}")
                            self.disconnect()
                            return False
                self.serial.flush()
            
            if icon_data:
                current_time = time.time()
                if current_time - self.last_icon_send < self.icon_send_timeout:
                    time.sleep(self.icon_send_timeout - (current_time - self.last_icon_send))
                
                # Log the message and icon data size
                print(f"Sent message before icon: {message.strip()}")
                print(f"Icon data size for {data.get('app', 'unknown')}: {len(icon_data)} bytes")
                
                # Wait for message to be processed
                time.sleep(0.1)
                
                # Send icon data with STX marker and in chunks
                self.serial.write(b'\x02')
                self.serial.flush()
                
                # Ensure icon_data is bytes
                if isinstance(icon_data, str):
                    icon_data = icon_data.encode('utf-8')
                elif not isinstance(icon_data, bytes):
                    icon_data = str(icon_data).encode('utf-8')
                
                # Send icon data in smaller chunks with retries
                for i in range(0, len(icon_data), chunk_size):
                    chunk = icon_data[i:i + chunk_size]
                    retries = 3
                    while retries > 0:
                        try:
                            bytes_written = self.serial.write(chunk)
                            if bytes_written > 0:
                                break
                            retries -= 1
                            time.sleep(0.01)
                        except Exception as e:
                            retries -= 1
                            time.sleep(0.01)
                            if retries == 0:
                                print(f"Failed to send icon chunk after retries: {str(e)}")
                                self.disconnect()
                                return False
                    self.serial.flush()
                    time.sleep(0.01)
                
                self.serial.write(b'\n')
                self.serial.flush()
                print(f"Finished sending icon data for: {data.get('app', 'unknown')}")
                self.last_icon_send = time.time()
                
            else:
                print(f"Sent: {message.strip()}")
            
            return True
            
        except Exception as e:
            print(f"Failed to send message: {e}")
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
            print(f"Processing message type: {msg_type}")
            
            if msg_type == "request_apps" or msg_type == "ready":
                app_volumes, icons = self.get_application_volumes()
                
                # Send app info first and wait for it to be processed
                self.send_message({
                    "type": "initial_config",
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
                        print(f"Failed to send icon for {icon_data['name']}")
                        break
                    
                    time.sleep(0.5)
                    
                # Send initialization complete message
                self.send_message({
                    "type": "init_complete"
                })
                    
        except Exception as e:
            print(f"Error handling message: {e}")
            
    def update(self):
        """Main update loop"""
        if not self.connected:
            if not self.connect():
                time.sleep(1)  # Wait before retry
                return
                
        try:
            # Check for incoming messages
            if self.serial and self.serial.is_open:
                try:
                    # Read with smaller chunks
                    if self.serial.in_waiting:
                        byte = self.serial.read(1)
                        if byte:
                            response_buffer = bytearray()
                            response_buffer.extend(byte)
                            
                            # Read until newline
                            while byte != b'\n' and self.serial.in_waiting:
                                byte = self.serial.read(1)
                                if byte:
                                    response_buffer.extend(byte)
                                    
                            if byte == b'\n':
                                try:
                                    line = response_buffer.decode().strip()
                                    if line:
                                        data = json.loads(line)
                                        self.handle_message(data)
                                except json.JSONDecodeError as e:
                                    print(f"Invalid JSON: {e}")
                                except Exception as e:
                                    print(f"Error processing message: {e}")
                                    
                except Exception as e:
                    print(f"Error reading message: {e}")
                    self.disconnect()
                    return
                    
            # Only send updates if we're fully initialized
            if self.initialized:
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
                        if not self.send_message({
                            "type": "app_changes",
                            "added": changes["added"],
                            "removed": changes["removed"],
                            "updated": changes["updated"]
                        }):
                            print("Failed to send app changes")
                            self.disconnect()
                            return
                        
                        # Update last app list
                        self.last_app_list = current_apps
                        
                    self.last_update = current_time
                    
            time.sleep(0.01)  # Small delay
            
        except Exception as e:
            print(f"Update error: {e}")
            self.disconnect()

    def send_icon_data(self, app_name, max_retries=3, retry_delay=1.0):
        """Send icon data for an app with retry logic"""
        try:
            if not self.serial or not self.serial.is_open:
                print("Cannot send icon data: Serial connection not open")
                return False
                
            # Get icon data
            icon_data = self.icon_handler.get_window_icon(app_name)
            if not icon_data:
                print(f"Failed to get icon for {app_name}, using default")
                icon_data = self.icon_handler.get_default_icon()
            
            if icon_data:
                for attempt in range(max_retries):
                    try:
                        # Send icon data message
                        self.send_message({
                            "type": "icon_data",
                            "app": app_name
                        })
                        
                        # Send raw RGB565 data with STX marker
                        self.serial.write(b'\x02')  # STX
                        self.serial.write(icon_data)
                        self.serial.write(b'\n')  # End marker
                        
                        print(f"Successfully sent icon for {app_name}")
                        return True
                        
                    except Exception as e:
                        print(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        raise
                        
        except Exception as e:
            print(f"Error sending icon data for {app_name}: {str(e)}")
        return False

    def connect(self):
        """Connect to Pico device and perform full initialization"""
        if not self.find_pico_com_port():
            return False
            
        try:
            # Wait for config request
            start_time = time.time()
            while time.time() - start_time < 5:  # 5 second timeout
                if self.serial.in_waiting:
                    try:
                        line = self.serial.readline().decode().strip()
                        if line:
                            data = json.loads(line)
                            if data.get("type") == "request_initial_config":
                                print("Received config request")
                                # Get and send initial configuration
                                app_volumes, icons = self.get_application_volumes()
                                if not self.send_message({
                                    "type": "initial_config",
                                    "data": app_volumes
                                }):
                                    print("Failed to send initial config")
                                    self.disconnect()
                                    return False
                                    
                                # Send icons one by one
                                for icon in icons:
                                    if not icon.get("icon"):
                                        continue
                                        
                                    # Send icon metadata
                                    if not self.send_message({
                                        "type": "icon_data",
                                        "app": icon["name"]
                                    }):
                                        print(f"Failed to send icon metadata for {icon['name']}")
                                        self.disconnect()
                                        return False
                                        
                                    # Wait for ready_for_icon
                                    ready_start = time.time()
                                    while time.time() - ready_start < 5:
                                        if self.serial.in_waiting:
                                            try:
                                                line = self.serial.readline().decode().strip()
                                                if line:
                                                    data = json.loads(line)
                                                    if (data.get("type") == "ready_for_icon" and 
                                                        data.get("app") == icon["name"]):
                                                        # Send icon data
                                                        if not self.send_message({
                                                            "type": "icon_data",
                                                            "app": icon["name"]
                                                        }, icon["icon"]):
                                                            print(f"Failed to send icon data for {icon['name']}")
                                                            self.disconnect()
                                                            return False
                                                        self.sent_icons.add(icon["name"])
                                                        break
                                            except Exception as e:
                                                print(f"Error processing ready_for_icon: {e}")
                                        time.sleep(0.1)
                                    else:
                                        print(f"Timeout waiting for ready_for_icon for {icon['name']}")
                                        self.disconnect()
                                        return False
                                        
                                    time.sleep(0.5)  # Delay between icons
                                    
                                # Send init complete
                                if not self.send_message({"type": "init_complete"}):
                                    print("Failed to send init complete")
                                    self.disconnect()
                                    return False
                                    
                                # Wait for ready response
                                ready_start = time.time()
                                while time.time() - ready_start < 5:
                                    if self.serial.in_waiting:
                                        try:
                                            line = self.serial.readline().decode().strip()
                                            if line:
                                                data = json.loads(line)
                                                if data.get("type") == "ready":
                                                    print("Device ready for updates")
                                                    self.initialized = True
                                                    self.connected = True
                                                    return True
                                        except Exception as e:
                                            print(f"Error processing ready response: {e}")
                                    time.sleep(0.1)
                                else:
                                    print("Timeout waiting for ready response")
                                    self.disconnect()
                                    return False
                    except Exception as e:
                        print(f"Error processing config request: {e}")
                time.sleep(0.1)
            else:
                print("No config request received")
                self.disconnect()
                return False
                
        except Exception as e:
            print(f"Connection failed: {e}")
            self.disconnect()
            return False

def main():
    monitor = VolumeMonitor()
    print("Volume Monitor starting...")
    
    try:
        while True:
            try:
                monitor.update()
            except KeyboardInterrupt:
                print("Shutting down...")
                monitor.disconnect()
                break
            except Exception as e:
                print(f"Main loop error: {e}")
                time.sleep(1)
    finally:
        monitor.disconnect()
        print("Volume Monitor stopped")

if __name__ == "__main__":
    main() 
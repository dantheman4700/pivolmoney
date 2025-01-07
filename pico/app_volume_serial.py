import machine
import json
import time
import usb.device
from usb.device.cdc import CDCInterface
import binascii

def log_to_file(msg):
    """Write log message to file"""
    try:
        with open('pico_serial.log', 'a') as f:
            f.write(str(msg) + '\n')
    except:
        pass

class AppVolumeController:
    def __init__(self):
        # Clear log file on startup
        try:
            with open('pico_serial.log', 'w') as f:
                f.write("")
        except:
            pass
            
        log_to_file("Initializing AppVolumeController")
        
        # Initialize USB CDC
        try:
            # Create CDC interface
            self.cdc = CDCInterface()
            
            # Get USB device singleton
            usb_dev = usb.device.get()
            
            # Initialize USB device with CDC interface
            usb_dev.init(self.cdc)
            log_to_file("USB device initialized with CDC interface")
            
            # Initialize CDC interface settings
            self.cdc.init(baudrate=115200, bits=8, parity='N', stop=1, timeout=100)
            log_to_file("USB CDC interface initialized")
            
            # Wait for USB host to configure the interface
            timeout = 50  # 5 seconds timeout
            while not self.cdc.is_open() and timeout > 0:
                time.sleep_ms(100)
                timeout -= 1
                log_to_file(f"Waiting for CDC interface... ({timeout})")
                
            if timeout <= 0:
                log_to_file("Timeout waiting for CDC interface to be opened")
                raise Exception("CDC interface timeout")
                
            log_to_file("CDC interface ready")
            
        except Exception as e:
            log_to_file(f"Error during CDC setup: {str(e)}")
            raise
            
        self.apps = {}
        self.connected = False
        self.update_count = 0
        self.input_buffer = bytearray()
        self.receiving_icon = False
        self.current_icon_data = bytearray()
        self.current_icon_app = None
        self.icon_start_marker = b'<ICON_START>'
        self.icon_end_marker = b'<ICON_END>'
        log_to_file("Initialization complete")
        
    def read_line(self):
        """Read a complete line from CDC Serial"""
        try:
            # Check if interface is ready
            if not self.cdc.is_open():
                return None
                
            # Try to read data (up to 256 bytes)
            data = self.cdc.read(256)
            if data:
                # Add to buffer
                self.input_buffer.extend(data)
                log_to_file(f"Read {len(data)} bytes")
                
                # Handle icon data mode
                if self.receiving_icon:
                    end_idx = self.input_buffer.find(self.icon_end_marker)
                    if end_idx != -1:
                        # Extract icon data
                        icon_data = self.input_buffer[:end_idx]
                        self.current_icon_data.extend(icon_data)
                        # Remove icon data and end marker from buffer
                        self.input_buffer = self.input_buffer[end_idx + len(self.icon_end_marker):]
                        # Process complete icon
                        if self.current_icon_app and self.current_icon_data:
                            try:
                                # Store raw icon data
                                clean_data = self.current_icon_data.replace(self.icon_start_marker, b'').replace(self.icon_end_marker, b'')
                                self.apps[self.current_icon_app]["icon"] = bytes(clean_data)
                                log_to_file(f"Stored icon for {self.current_icon_app} ({len(clean_data)} bytes)")
                            except Exception as e:
                                log_to_file(f"Error storing icon: {str(e)}")
                        # Reset icon receiving state
                        self.receiving_icon = False
                        self.current_icon_data = bytearray()
                        self.current_icon_app = None
                    else:
                        # Still receiving icon data
                        received_size = len(self.current_icon_data)
                        new_size = len(self.input_buffer)
                        self.current_icon_data.extend(self.input_buffer)
                        log_to_file(f"Received {new_size} bytes of icon data for {self.current_icon_app} (total: {received_size + new_size})")
                        self.input_buffer = bytearray()
                    return None
                
                # Look for icon start marker
                start_idx = self.input_buffer.find(self.icon_start_marker)
                if start_idx != -1:
                    # Process any complete line before the icon data
                    if start_idx > 0:
                        try:
                            line = self.input_buffer[:start_idx].decode().strip()
                            if line:
                                # Split by newlines in case multiple messages got combined
                                lines = line.split('\n')
                                for single_line in lines:
                                    if single_line.strip():
                                        try:
                                            # Validate it's proper JSON
                                            json.loads(single_line.strip())
                                            log_to_file(f"Found valid JSON before icon: {single_line.strip()}")
                                            # Process this message immediately
                                            self.handle_message(json.loads(single_line.strip()))
                                        except Exception as e:
                                            log_to_file(f"Invalid JSON before icon: {single_line.strip()} - {str(e)}")
                        except:
                            pass
                    
                    # Enter icon receiving mode
                    self.receiving_icon = True
                    self.current_icon_data = bytearray()
                    # Remove start marker
                    self.input_buffer = self.input_buffer[start_idx + len(self.icon_start_marker):]
                    return None
                
                # Look for complete lines
                while b'\n' in self.input_buffer:
                    try:
                        newline_index = self.input_buffer.index(b'\n')
                        # Extract the line
                        line = self.input_buffer[:newline_index].decode().strip()
                        # Remove processed data from buffer
                        self.input_buffer = self.input_buffer[newline_index + 1:]
                        if line:
                            try:
                                # Validate it's proper JSON before returning
                                json.loads(line)
                                log_to_file(f"Found complete line: {line}")
                                return line
                            except Exception as e:
                                log_to_file(f"Invalid JSON: {line} - {str(e)}")
                    except ValueError:
                        break
                    except Exception as e:
                        log_to_file(f"Error processing line: {str(e)}")
                        break
                
                # Check buffer size
                if len(self.input_buffer) > 1024:  # Prevent buffer from growing too large
                    log_to_file("Buffer too large, clearing")
                    self.input_buffer = bytearray()
                    
        except Exception as e:
            log_to_file(f"Error reading line: {str(e)}")
            self.input_buffer = bytearray()  # Clear buffer on error
            self.receiving_icon = False
            self.current_icon_data = bytearray()
            
        return None
        
    def send_message(self, data):
        try:
            if not self.cdc.is_open():
                log_to_file("Cannot send - CDC not open")
                return False
                
            message = json.dumps(data) + '\n'
            bytes_written = self.cdc.write(message.encode())
            if bytes_written > 0:
                log_to_file(f"Sent message ({bytes_written} bytes): {message.strip()}")
                return True
            else:
                log_to_file("No bytes written")
                return False
        except Exception as e:
            log_to_file(f"Send error: {str(e)}")
            return False
            
    def handle_message(self, data):
        try:
            msg_type = data.get("type", "")
            log_to_file(f"Processing message type: {msg_type}")
            
            if msg_type == "test":
                log_to_file("Received test message, sending response")
                self.send_message({"type": "test_response", "status": "ready"})
                
            elif msg_type == "connected":
                log_to_file("Connection established")
                self.connected = True
                
            elif msg_type == "initial_config":
                old_count = len(self.apps)
                try:
                    # Store basic app info
                    new_apps = {}
                    for app in data.get("data", []):
                        app_name = app.get("name")
                        if app_name:
                            new_apps[app_name] = app
                            if app.get("has_icon"):
                                log_to_file(f"App {app_name} has icon flag set")
                    self.apps = new_apps
                    log_to_file(f"Initial config received: {old_count} -> {len(self.apps)} apps")
                except Exception as e:
                    log_to_file(f"Error processing initial config: {str(e)}")
                
            elif msg_type == "icon_data":
                app_name = data.get("app")
                if app_name and app_name in self.apps:
                    self.current_icon_app = app_name
                    log_to_file(f"Expecting icon data for {app_name}")
                    # Log current icon state
                    has_icon = "icon" in self.apps[app_name]
                    log_to_file(f"Current icon state for {app_name}: {'has icon' if has_icon else 'no icon'}")
                else:
                    log_to_file(f"Received icon data for unknown app: {app_name}")
                    
            elif msg_type == "init_complete":
                log_to_file("Initialization complete")
                # Log icon status for all apps
                log_to_file("App icon status:")
                for app_name, app in self.apps.items():
                    has_icon = "icon" in app
                    log_to_file(f"  {app_name}: {'has icon' if has_icon else 'no icon'}")
                self.send_message({"type": "ready"})
                
            elif msg_type == "app_changes":
                try:
                    # Handle added apps
                    for app in data.get("added", []):
                        app_name = app.get("name")
                        if app_name:
                            self.apps[app_name] = app
                            log_to_file(f"Added app: {app_name} (has_icon flag: {app.get('has_icon', False)})")
                    
                    # Handle removed apps
                    for app_name in data.get("removed", []):
                        if app_name in self.apps:
                            had_icon = "icon" in self.apps[app_name]
                            del self.apps[app_name]
                            log_to_file(f"Removed app: {app_name} (had icon: {had_icon})")
                    
                    # Handle updated apps
                    for app in data.get("updated", []):
                        app_name = app.get("name")
                        if app_name and app_name in self.apps:
                            # Preserve icon if it exists
                            had_icon = "icon" in self.apps[app_name]
                            if had_icon:
                                app["icon"] = self.apps[app_name]["icon"]
                            self.apps[app_name] = app
                            log_to_file(f"Updated app: {app_name} (preserved icon: {had_icon})")
                    
                    log_to_file(f"Processed app changes - current app count: {len(self.apps)}")
                    # Log current icon status
                    apps_with_icons = sum(1 for app in self.apps.values() if "icon" in app)
                    log_to_file(f"Apps with icons: {apps_with_icons}/{len(self.apps)}")
                except Exception as e:
                    log_to_file(f"Error processing app changes: {str(e)}")
                
        except Exception as e:
            log_to_file(f"Handle message error: {str(e)}")
    
    def update(self):
        try:
            # Check CDC status periodically
            self.update_count += 1
            if self.update_count % 100 == 0:
                is_open = self.cdc.is_open()
                log_to_file(f"Status - CDC open: {is_open}, Connected: {self.connected}, Apps: {len(self.apps)}")
                
            # Read and process any available messages
            line = self.read_line()
            if line:
                try:
                    data = json.loads(line)
                    self.handle_message(data)
                except Exception as e:
                    log_to_file(f"Error processing message: {str(e)}")
                    
        except Exception as e:
            log_to_file(f"Update error: {str(e)}")
            
        time.sleep(0.01)  # Small delay to prevent tight loop 
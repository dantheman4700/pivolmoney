import machine
import json
import time
import usb.device
from usb.device.cdc import CDCInterface

def log_to_file(message):
    """Write log message to file with timestamp"""
    try:
        with open('pico_serial.log', 'a') as f:
            timestamp = time.localtime()
            time_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                timestamp[0], timestamp[1], timestamp[2],
                timestamp[3], timestamp[4], timestamp[5]
            )
            f.write(f"{time_str} - {message}\n")
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
                
                # Look for complete line
                try:
                    newline_index = self.input_buffer.index(b'\n')
                    # Extract the line
                    line = self.input_buffer[:newline_index].decode().strip()
                    # Remove processed data from buffer
                    self.input_buffer = self.input_buffer[newline_index + 1:]
                    if line:
                        log_to_file(f"Found complete line: {line}")
                        return line
                except ValueError:
                    # No complete line yet
                    if len(self.input_buffer) > 1024:  # Prevent buffer from growing too large
                        log_to_file("Buffer too large, clearing")
                        self.input_buffer = bytearray()
                    pass
                    
        except Exception as e:
            log_to_file(f"Error reading line: {str(e)}")
            self.input_buffer = bytearray()  # Clear buffer on error
            
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
                self.send_message({"type": "request_apps"})
                
            elif msg_type == "apps_update":
                old_count = len(self.apps)
                self.apps = {app["name"]: app for app in data["data"]}
                log_to_file(f"Updated apps: {old_count} -> {len(self.apps)}")
                
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
                except json.JSONDecodeError as e:
                    log_to_file(f"Invalid JSON: {line} ({str(e)})")
                except Exception as e:
                    log_to_file(f"Error processing message: {str(e)}")
                    
        except Exception as e:
            log_to_file(f"Update error: {str(e)}")
            
        time.sleep(0.01)  # Small delay to prevent tight loop 
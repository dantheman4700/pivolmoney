import sys
import select
import json
import time
import os

def clear_log_file():
    """Clear the log file"""
    try:
        with open('serial.log', 'w') as f:
            f.write("")  # Clear file
    except Exception as e:
        print(f"Error clearing log file: {e}", file=sys.stderr)

def log_to_file(message, clear_on_first=False):
    """Write log message to file
    Args:
        message: Message to log
        clear_on_first: If True, clear log file on first write
    """
    try:
        # Clear file if this is the first write and clear_on_first is True
        if clear_on_first and not hasattr(log_to_file, "_initialized"):
            clear_log_file()
            log_to_file._initialized = True
        
        # Make sure we're writing to a location we can access
        log_path = 'serial.log'
        
        # Try to create/append to the file to verify we can write
        with open(log_path, 'a') as f:
            timestamp = time.localtime()
            time_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                timestamp[0], timestamp[1], timestamp[2],
                timestamp[3], timestamp[4], timestamp[5]
            )
            log_line = f"{time_str} - {message}\n"
            f.write(log_line)
            f.flush()  # Force write to file
    except Exception as e:
        print(f"Logging error: {e}", file=sys.stderr)
        # Also try to write to stderr for visibility in Thonny
        print(f"{message}", file=sys.stderr)

class AppVolumeController:
    def __init__(self, update_callback=None, clear_logs=True):
        self.apps = []
        self.selected_app = None
        self.update_callback = update_callback
        self.last_request_time = 0
        self.request_interval = 1.0  # How often to request updates (seconds)
        
        # Clear logs if requested
        if clear_logs:
            clear_log_file()
        
        log_to_file("AppVolumeController initialized")
        
    def init_serial(self):
        """Initialize serial communication"""
        max_retries = 5
        retry_count = 0
        
        # Log buffer types for debugging
        log_to_file(f"stdin buffer type: {type(sys.stdin.buffer)}")
        log_to_file(f"stdout buffer type: {type(sys.stdout.buffer)}")
        
        while retry_count < max_retries:
            try:
                log_to_file("Starting serial initialization")
                
                # Clear any pending data, but don't block if no data
                log_to_file("Clearing input buffer")
                if select.select([sys.stdin], [], [], 0)[0]:
                    sys.stdin.buffer.read()
                
                # Test serial communication
                log_to_file("Sending test message")
                test_msg = {"type": "test", "message": "Serial test"}
                if not self.send_serial_data(test_msg):
                    log_to_file("Failed to send test message")
                    retry_count += 1
                    time.sleep(1)
                    continue
                
                # Wait for response
                log_to_file("Waiting for PC response")
                for _ in range(5):  # Try multiple times to get response
                    data = self.read_serial_data()
                    if data:
                        log_to_file(f"Got response: {data}")
                        if data.get("type") == "test_response" and data.get("status") == "ok":
                            log_to_file("Valid response received - connection established")
                            return True
                    time.sleep(0.2)
                
                log_to_file("No valid response received, retrying...")
                retry_count += 1
                time.sleep(1)
                
            except Exception as e:
                log_to_file(f"Serial init error: {e}")
                retry_count += 1
                time.sleep(1)
        
        log_to_file("Failed to initialize serial after max retries")
        return False
    
    def read_serial_data(self):
        """Read data from serial if available"""
        try:
            if select.select([sys.stdin], [], [], 0)[0]:
                # Read raw bytes and decode
                try:
                    # Read one byte at a time until newline
                    data = bytearray()
                    while True:
                        byte = sys.stdin.buffer.read(1)
                        if not byte:  # EOF
                            break
                        data.extend(byte)
                        if byte == b'\n':
                            break
                    
                    if data:
                        decoded_data = data.decode('utf-8').strip()
                        if decoded_data:  # Only log if we actually got data
                            log_to_file(f"Received data: {decoded_data}")
                            try:
                                return json.loads(decoded_data)
                            except json.JSONDecodeError as e:
                                log_to_file(f"JSON decode error: {e}")
                                return None
                except Exception as e:
                    log_to_file(f"Error reading bytes: {e}")
            return None
        except Exception as e:
            log_to_file(f"Error reading serial: {e}")
            return None
    
    def send_serial_data(self, data):
        """Send data over serial"""
        try:
            json_str = json.dumps(data)
            # Write bytes directly to stdout buffer
            sys.stdout.buffer.write((json_str + '\n').encode('utf-8'))
            # No need to flush - MicroPython's stdout buffer is unbuffered
            log_to_file(f"Sent data: {json_str}")
            return True
        except Exception as e:
            log_to_file(f"Error sending serial: {e}")
            return False
    
    def request_app_list(self):
        """Request updated app list from PC"""
        current_time = time.time()
        if current_time - self.last_request_time >= self.request_interval:
            log_to_file("Requesting app list update")
            self.send_serial_data({"type": "request_apps"})
            self.last_request_time = current_time
    
    def set_app_volume(self, app_name, volume):
        """Set volume for specific app"""
        log_to_file(f"Setting volume for {app_name} to {volume}")
        return self.send_serial_data({
            "type": "set_volume",
            "app": app_name,
            "volume": volume
        })
    
    def toggle_app_mute(self, app_name=None):
        """Toggle mute for app or system"""
        log_to_file(f"Toggling mute for {'system' if app_name is None else app_name}")
        return self.send_serial_data({
            "type": "toggle_mute",
            "app": app_name
        })
    
    def handle_message(self, data):
        """Handle incoming messages from PC"""
        try:
            if data["type"] == "test_response":
                log_to_file("Received test response from PC")
                return
                
            elif data["type"] == "apps" or data["type"] == "apps_update":
                self.apps = data["data"]
                log_to_file(f"Updated app list: {len(self.apps)} apps")
                if self.update_callback:
                    self.update_callback(self.apps)
                
            elif data["type"] == "volume_set":
                success = data.get("success", False)
                log_to_file(f"Volume set result for {data['app']}: {'success' if success else 'failed'}")
                
            elif data["type"] == "mute_toggled":
                success = data.get("success", False)
                log_to_file(f"Mute toggle result for {data['app']}: {'success' if success else 'failed'}")
                
            elif data["type"] == "error":
                log_to_file(f"Error from PC: {data['message']}")
                
        except Exception as e:
            log_to_file(f"Error handling message: {e}")
    
    def update(self):
        """Main update function to be called in the event loop"""
        try:
            # Check for incoming messages
            data = self.read_serial_data()
            if data:
                self.handle_message(data)
            
            # Periodically request app list updates
            self.request_app_list()
            
        except Exception as e:
            log_to_file(f"Update error: {e}")
            # Don't return/exit on error, just log it
    
    def get_apps(self):
        """Get current app list"""
        return self.apps
    
    def find_app(self, app_name):
        """Find app in current list"""
        for app in self.apps:
            if app["name"] == app_name:
                return app
        return None

# Message formats:
# From PC to Pico:
# {"type": "apps", "data": [{"name": "Chrome", "volume": 75, "muted": false}, ...]}
# {"type": "volume_set", "success": true, "app": "Chrome"}
# {"type": "mute_toggled", "success": true, "app": "Chrome"}
# {"type": "error", "message": "Error message"}
# 
# From Pico to PC:
# {"type": "request_apps"}
# {"type": "set_volume", "app": "Chrome", "volume": 50}
# {"type": "toggle_mute", "app": "Chrome"} 
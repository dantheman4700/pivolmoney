import json
import time
import sys
import select
from core.logger import get_logger
from core.config import (
    SERIAL_BUFFER_SIZE, SERIAL_TIMEOUT_MS, RECONNECT_DELAY_MS,
    HEARTBEAT_INTERVAL_MS, ICON_START_MARKER, ICON_END_MARKER,
    MessageType
)
from communication.media_control import MediaControlHID

# For older MicroPython versions that don't have JSONDecodeError in json module
try:
    from json import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError  # Use ValueError as fallback

class CommunicationManager:
    def __init__(self):
        self.logger = get_logger()
        self.media_control = None
        self.connected = False
        self.hardware_initialized = False  # Hardware initialization state
        self.protocol_initialized = False  # Protocol/handshake completion state
        self.apps = {}
        self.update_count = 0
        self.input_buffer = bytearray()
        self.receiving_icon = False
        self.current_icon_data = bytearray()
        self.current_icon_app = None
        self.icon_start_marker = ICON_START_MARKER
        self.icon_end_marker = ICON_END_MARKER
        self.icon_callback = None
        self.last_heartbeat = time.ticks_ms()
        self.poll = select.poll()
        self.poll.register(sys.stdin, select.POLLIN)
        self.expected_icons = 0  # Track how many icons we expect
        self.received_icons = 0  # Track how many icons we've received
        self.processing_icon = False  # Flag to prevent duplicate icon processing
        
    def initialize(self):
        """Initialize communication interfaces"""
        try:
            # Reset state
            self.hardware_initialized = False
            self.protocol_initialized = False
            self.connected = False
            self.input_buffer = bytearray()
            
            # Initialize HID interface first
            self.media_control = MediaControlHID.get_instance()
            if not self.media_control.initialize():
                self.logger.error("Failed to initialize HID interface")
                return False
            
            # Clear any pending data from REPL
            while self.poll.poll(0):  # Non-blocking poll
                sys.stdin.read(1)
            
            self.logger.info("All interfaces initialized successfully")
            self.hardware_initialized = True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize communication: {str(e)}")
            return False
            
    def read_line(self):
        """Read a complete line from REPL"""
        if not self.hardware_initialized:
            return None
            
        try:
            # Check if there's data available
            if self.poll.poll(0):  # Non-blocking poll
                # Read one byte at a time
                line = bytearray()
                while True:
                    if not self.poll.poll(0):
                        time.sleep_ms(1)
                        continue
                        
                    byte = sys.stdin.read(1)
                    if byte == '\x03':  # Ctrl+C
                        self.logger.info("Received keyboard interrupt")
                        raise KeyboardInterrupt
                    
                    # For normal messages, accumulate until newline
                    # Skip any REPL output (lines starting with >>>)
                    if byte == '>':
                        # Skip the rest of the REPL prompt
                        while byte != '\n' and self.poll.poll(0):
                            byte = sys.stdin.read(1)
                        continue
                        
                    line.extend(byte.encode())
                    if byte == '\n':
                        break
                    
                try:
                    # Only try to decode as string if we have a complete line
                    line_str = line.decode().strip()
                    if not line_str:
                        return None
                        
                    try:
                        data = json.loads(line_str)
                        self.logger.info(f"Valid message received: {line_str}")
                        
                        # Handle base64 encoded icon data
                        if data.get("type") == "icon_data_b64":
                            import binascii
                            app_name = data.get("app")
                            b64_data = data.get("data")
                            
                            if app_name and b64_data and app_name in self.apps and not self.processing_icon:
                                self.processing_icon = True  # Set processing flag
                                try:
                                    # Decode base64 data using binascii
                                    icon_data = binascii.a2b_base64(b64_data)
                                    self.logger.info(f"Decoded icon data for {app_name}, size: {len(icon_data)} bytes")
                                    
                                    # Verify size is correct (48x48x2 = 4608 bytes)
                                    if len(icon_data) != 4608:
                                        raise ValueError(f"Invalid icon size: {len(icon_data)} bytes")
                                    
                                    # Store the icon data
                                    self.apps[app_name]["icon"] = icon_data
                                    self.received_icons += 1
                                    self.logger.info(f"Received {self.received_icons}/{self.expected_icons} icons")
                                    
                                    # Send confirmation
                                    confirm = {
                                        "type": "icon_parsed",
                                        "app": app_name,
                                        "status": "ok"
                                    }
                                    self.send_message(confirm)
                                except Exception as e:
                                    self.logger.error(f"Error decoding icon data: {str(e)}")
                                    # Send error confirmation
                                    error = {
                                        "type": "icon_parsed",
                                        "app": app_name,
                                        "status": "error",
                                        "error": str(e)
                                    }
                                    self.send_message(error)
                                finally:
                                    self.processing_icon = False  # Clear processing flag
                            return None
                            
                        elif data.get("type") == "icon_data":
                            # Only process if not already processing an icon and we haven't received this icon yet
                            app_name = data.get("app")
                            if (app_name and app_name in self.apps and 
                                not self.processing_icon and 
                                not self.apps[app_name].get("icon")):  # Check if we already have the icon
                                
                                self.processing_icon = True
                                try:
                                    # Send ready for icon message
                                    self.current_icon_app = app_name
                                    self.logger.info(f"Starting icon data reception for {self.current_icon_app}")
                                    ready = {
                                        "type": "ready_for_icon",
                                        "app": self.current_icon_app
                                    }
                                    self.send_message(ready)
                                finally:
                                    self.processing_icon = False
                            else:
                                if self.processing_icon:
                                    self.logger.info("Already processing an icon, skipping request")
                                elif app_name not in self.apps:
                                    self.logger.warning(f"Received icon data for unknown app: {app_name}")
                                elif self.apps[app_name].get("icon"):
                                    self.logger.info(f"Already have icon for {app_name}, skipping request")
                            return None
                            
                        return line_str
                        
                    except (ValueError, JSONDecodeError) as e:
                        # Only log error if it's not binary data
                        if not any(b > 127 for b in line):
                            self.logger.error(f"Invalid JSON message: {line_str[:100]}")
                except Exception as e:
                    self.logger.error(f"Invalid message: {str(e)}")
            
        except KeyboardInterrupt:
            raise
        except Exception as e:
            self.logger.debug(f"Read error: {str(e)}")
            
        return None
        
    def send_message(self, data):
        """Send message through REPL"""
        if not self.hardware_initialized:
            self.logger.error("Cannot send message - not initialized")
            return False
        
        try:
            message = json.dumps(data) + '\n'
            print(message, end='')  # Use print instead of sys.stdout for REPL
            self.logger.debug(f"Sent message: {message.strip()}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send message: {str(e)}")
            return False
            
    def handle_message(self, data):
        """Handle incoming messages"""
        try:
            msg_type = data.get("type", "")
            self.logger.info(f"Processing message type: {msg_type}")
            
            if msg_type == "test":
                self.logger.info("Received test message, sending response")
                response = {
                    "type": "test_response",
                    "status": "ok"
                }
                if self.send_message(response):
                    self.logger.info("Test response sent successfully")
                    # After successful handshake, request initial config
                    time.sleep_ms(100)  # Small delay before requesting config
                    config_request = {
                        "type": "request_initial_config"
                    }
                    if self.send_message(config_request):
                        self.logger.info("Initial config requested")
                        self.connected = True
                    else:
                        self.logger.error("Failed to request initial config")
                else:
                    self.logger.error("Failed to send test response")
                
            elif msg_type == "initial_config":
                self.logger.info("Received initial config")
                try:
                    # Store basic app info and count expected icons
                    new_apps = {}
                    self.expected_icons = 0
                    seen_apps = set()  # Track unique apps
                    
                    for app in data.get("data", []):
                        app_name = app.get("name")
                        if app_name and app_name not in seen_apps:  # Only process unique apps
                            seen_apps.add(app_name)
                            new_apps[app_name] = app
                            if app.get("has_icon", False):
                                self.expected_icons += 1
                    
                    self.apps = new_apps
                    self.received_icons = 0  # Reset received icons counter
                    self.logger.info(f"Processed {len(self.apps)} unique apps from initial config, expecting {self.expected_icons} icons")
                    
                    # Send confirmation
                    confirm = {
                        "type": "config_received",
                        "status": "ok",
                        "unique_apps": len(self.apps)
                    }
                    if not self.send_message(confirm):
                        self.logger.error("Failed to send config confirmation")
                        
                except Exception as e:
                    self.logger.error(f"Error processing initial config: {str(e)}")
                    
            elif msg_type == "icon_data":
                app_name = data.get("app")
                if app_name and app_name in self.apps and not self.processing_icon:
                    self.processing_icon = True
                    try:
                        self.current_icon_app = app_name
                        self.logger.info(f"Expecting icon data for {app_name}")
                        # Send confirmation that we're ready for icon
                        ready = {
                            "type": "ready_for_icon",
                            "app": app_name
                        }
                        if not self.send_message(ready):
                            self.logger.error("Failed to send ready_for_icon")
                    finally:
                        self.processing_icon = False
                else:
                    if self.processing_icon:
                        self.logger.info("Already processing an icon, skipping request")
                    elif app_name not in self.apps:
                        self.logger.warning(f"Received icon data for unknown app: {app_name}")
                    
            elif msg_type == "init_complete":
                self.logger.info("Initialization complete")
                # Only switch to full UI if we've received all expected icons
                if self.received_icons == self.expected_icons:
                    # Switch to full UI mode
                    from core.config import UIState
                    from ui.ui_manager import UIManager
                    ui_manager = UIManager.get_instance()
                    if ui_manager:
                        ui_manager.set_state(UIState.FULL_UI)
                        self.logger.info("Switched to full UI mode")
                    
                    # Send ready message
                    ready = {
                        "type": "ready",
                        "status": "ok"
                    }
                    if self.send_message(ready):
                        self.protocol_initialized = True
                        self.logger.info("Ready for updates")
                    else:
                        self.logger.error("Failed to send ready response")
                else:
                    self.logger.warning(f"Not all icons received: {self.received_icons}/{self.expected_icons}")
                
        except Exception as e:
            self.logger.error(f"Handle message error: {str(e)}")
            if self.processing_icon:
                self.processing_icon = False  # Reset processing flag on error
            
    def update(self):
        """Main update loop"""
        if not self.hardware_initialized:
            return
            
        try:
            # Read and process any available messages
            line = self.read_line()
            if line:
                try:
                    data = json.loads(line)
                    self.handle_message(data)
                except Exception as e:
                    self.logger.error(f"Error processing message: {str(e)}")
                    
        except Exception as e:
            self.logger.error(f"Update error: {str(e)}")
            
        time.sleep_ms(10)  # Small delay to prevent tight loop 
        
    def cleanup(self):
        """Cleanup resources"""
        try:
            if self.poll:
                self.poll.unregister(sys.stdin)
        except Exception as e:
            self.logger.error(f"Cleanup error: {str(e)}") 
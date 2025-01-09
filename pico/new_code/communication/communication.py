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
                # Read one byte at a time until newline
                line = bytearray()
                while True:
                    if not self.poll.poll(0):
                        time.sleep_ms(1)
                        continue
                        
                    byte = sys.stdin.read(1)
                    if byte == '\x03':  # Ctrl+C
                        self.logger.info("Received keyboard interrupt")
                        raise KeyboardInterrupt
                        
                    line.extend(byte.encode())
                    if byte == '\n':
                        break
                    
                try:
                    # Convert to string and validate JSON
                    line_str = line.decode().strip()
                    if line_str:
                        data = json.loads(line_str)
                        self.logger.info(f"Valid message received: {line_str}")
                        return line_str
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
            sys.stdout.write(message)
            sys.stdout.flush()
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
                    if self.send_message({"type": "request_initial_config"}):
                        self.logger.info("Initial config requested")
                        self.connected = True
                    else:
                        self.logger.error("Failed to request initial config")
                else:
                    self.logger.error("Failed to send test response")
                
            elif msg_type == "initial_config":
                old_count = len(self.apps)
                try:
                    # Store basic app info
                    new_apps = {}
                    for app in data.get("data", []):
                        app_name = app.get("name")
                        if app_name:
                            new_apps[app_name] = app
                    self.apps = new_apps
                    self.logger.info(f"Initial config received: {old_count} -> {len(self.apps)} apps")
                    # Send confirmation
                    self.send_message({
                        "type": "config_received",
                        "status": "ok"
                    })
                except Exception as e:
                    self.logger.error(f"Error processing initial config: {str(e)}")
                    
            elif msg_type == "icon_data":
                app_name = data.get("app")
                if app_name and app_name in self.apps:
                    self.current_icon_app = app_name
                    self.logger.info(f"Expecting icon data for {app_name}")
                    # Send confirmation that we're ready for icon
                    self.send_message({
                        "type": "ready_for_icon",
                        "app": app_name
                    })
                else:
                    self.logger.warning(f"Received icon data for unknown app: {app_name}")
                    
            elif msg_type == "init_complete":
                self.logger.info("Initialization complete")
                if self.send_message({"type": "ready", "status": "ok"}):
                    self.protocol_initialized = True
                    self.logger.info("Ready for updates")
                else:
                    self.logger.error("Failed to send ready response")
                
        except Exception as e:
            self.logger.error(f"Handle message error: {str(e)}")
            
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
import json
import time
import sys
import select
from usb.device.cdc import CDCInterface  # Changed import
import usb.device
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
        self.cdc = None  # Will be initialized later
        self.expected_icons = 0  # Track how many icons we expect
        self.received_icons = 0  # Track how many icons we've received
        self.processing_icon = False  # Flag to prevent duplicate icon processing
        self.ui_manager = None  # Reference to UI manager
        
    def initialize(self):
        """Initialize communication interfaces"""
        try:
            # Reset state
            self.hardware_initialized = False
            self.protocol_initialized = False
            self.connected = False
            self.input_buffer = bytearray()
            
            # Get reference to UI manager
            from ui.ui_manager import UIManager
            self.ui_manager = UIManager.get_instance()
            
            # Create interfaces but don't initialize yet
            self.media_control = MediaControlHID.get_instance()
            self.cdc = CDCInterface()
            self.cdc.init(timeout=0)  # Non-blocking mode
            
            # Initialize USB device with both interfaces
            usb.device.get().init(self.cdc, builtin_driver=True)
            
            # Wait for USB host to configure the interfaces
            self.logger.info("Waiting for USB host to configure interfaces...")
            timeout = time.ticks_add(time.ticks_ms(), 5000)  # 5 second timeout
            
            while not self.cdc.is_open():
                if time.ticks_diff(time.ticks_ms(), timeout) >= 0:
                    self.logger.error("Timeout waiting for interfaces")
                    return False
                time.sleep_ms(100)
            
            self.logger.info("CDC interface configured successfully")
            
            # Now initialize HID interface
            if not self.media_control.initialize():
                self.logger.error("Failed to initialize HID interface")
                return False
            
            # Register CDC interface with poll
            self.poll.register(self.cdc, select.POLLIN)
            
            self.logger.info("All interfaces initialized successfully")
            self.hardware_initialized = True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize communication: {str(e)}")
            return False
            
    def read_line(self):
        """Read a line from CDC interface"""
        if not self.hardware_initialized or not self.cdc:
            return None
            
        try:
            if self.poll.poll(SERIAL_TIMEOUT_MS):
                return self.cdc.readline().decode().strip()
            return None
        except Exception as e:
            self.logger.error(f"Error reading line: {str(e)}")
            return None
        
    def send_message(self, data):
        """Send message through CDC interface"""
        if not self.hardware_initialized or not self.cdc:
            self.logger.error("Cannot send message - not initialized")
            return False
            
        try:
            message = json.dumps(data) + '\n'
            self.cdc.write(message.encode())
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
                    # Update UI manager's app data
                    if self.ui_manager:
                        self.ui_manager.apps = new_apps
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

            elif msg_type == "volume_update":
                app_name = data.get("app")
                volume = data.get("volume")
                if app_name and volume is not None:
                    if app_name in self.apps:
                        # Preserve icon if it exists
                        if "icon" in self.apps[app_name]:
                            icon_data = self.apps[app_name]["icon"]
                            self.apps[app_name]["volume"] = volume
                            self.apps[app_name]["icon"] = icon_data
                        else:
                            self.apps[app_name]["volume"] = volume
                        # Update UI if we have a UI manager
                        if self.ui_manager:
                            self.ui_manager.handle_volume_update(app_name, volume)
                    else:
                        self.logger.warning(f"Volume update for unknown app: {app_name}")

            elif msg_type == "mute_update":
                app_name = data.get("app")
                muted = data.get("muted")
                if app_name and muted is not None:
                    if app_name in self.apps:
                        # Preserve icon if it exists
                        if "icon" in self.apps[app_name]:
                            icon_data = self.apps[app_name]["icon"]
                            self.apps[app_name]["muted"] = muted
                            self.apps[app_name]["icon"] = icon_data
                        else:
                            self.apps[app_name]["muted"] = muted
                        # Update UI if we have a UI manager
                        if self.ui_manager:
                            self.ui_manager.handle_mute_update(app_name, muted)
                    else:
                        self.logger.warning(f"Mute update for unknown app: {app_name}")

            elif msg_type == "app_changes":
                added = data.get("added", [])
                removed = data.get("removed", [])
                updated = data.get("updated", [])
                
                # Handle added apps
                for app in added:
                    app_name = app.get("name")
                    if app_name:
                        self.apps[app_name] = app
                
                # Handle removed apps
                for app_name in removed:
                    if app_name in self.apps:
                        del self.apps[app_name]
                
                # Handle updated apps
                for app in updated:
                    app_name = app.get("name")
                    if app_name in self.apps:
                        # Preserve icon if it exists
                        if "icon" in self.apps[app_name]:
                            icon_data = self.apps[app_name]["icon"]
                            self.apps[app_name].update(app)
                            self.apps[app_name]["icon"] = icon_data
                        else:
                            self.apps[app_name].update(app)
                
                # Update UI manager's app data and redraw only if needed
                if self.ui_manager:
                    self.ui_manager.apps = self.apps
                    if added or removed:
                        # Only redraw app list if apps were added/removed
                        self.ui_manager.draw_app_list()
                    elif updated:
                        # For updates, only redraw center panel if selected app was updated
                        for app in updated:
                            if app.get("name") == self.ui_manager.selected_app:
                                self.ui_manager.draw_center_panel(
                                    app.get("name"),
                                    app.get("volume", 0)
                                )
                                break

            elif msg_type == "icon_data_b64":
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
                        # Update UI manager's app data
                        if self.ui_manager:
                            self.ui_manager.apps[app_name]["icon"] = icon_data
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
                else:
                    if self.processing_icon:
                        self.logger.info("Already processing an icon, skipping request")
                    elif app_name not in self.apps:
                        self.logger.warning(f"Received icon data for unknown app: {app_name}")
                    elif self.apps[app_name].get("icon"):
                        self.logger.info(f"Already have icon for {app_name}, skipping request")

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
                self.poll.unregister(self.cdc)
        except Exception as e:
            self.logger.error(f"Cleanup error: {str(e)}")
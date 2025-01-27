import json
import time
import sys
from core.logger import get_logger
import usb.device
from usb.device.cdc import CDCInterface
from usb.device.hid import HIDInterface

# For older MicroPython versions that don't have JSONDecodeError in json module
try:
    from json import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError  # Use ValueError as fallback

class MediaHIDInterface(HIDInterface):
    """HID interface for media controls"""
    def __init__(self):
        # HID Report descriptor for consumer control
        report_descriptor = bytes([
            0x05, 0x0C,        # Usage Page (Consumer)
            0x09, 0x01,        # Usage (Consumer Control)
            0xA1, 0x01,        # Collection (Application)
            0x15, 0x00,        # Logical Minimum (0)
            0x25, 0x01,        # Logical Maximum (1)
            0x75, 0x01,        # Report Size (1)
            0x95, 0x06,        # Report Count (6)
            0x09, 0xE2,        # Usage (Mute)           - bit 0
            0x09, 0xE9,        # Usage (Volume Up)      - bit 1
            0x09, 0xEA,        # Usage (Volume Down)    - bit 2
            0x09, 0xCD,        # Usage (Play/Pause)     - bit 3
            0x09, 0xB5,        # Usage (Next Track)     - bit 4
            0x09, 0xB6,        # Usage (Previous Track) - bit 5
            0x81, 0x02,        # Input (Data, Variable, Absolute)
            0x95, 0x02,        # Report Count (2)
            0x81, 0x01,        # Input (Constant)       - 2 padding bits
            0xC0               # End Collection
        ])
        
        super().__init__(
            report_descriptor=report_descriptor,
            interface_str="MicroPython Media Controls"
        )
        
    def send_control(self, control, duration_ms=100):
        """Send a media control command with automatic release"""
        try:
            self.send_report(bytes([control]))
            time.sleep_ms(duration_ms)
            self.send_report(b"\x00")  # Release
            return True
        except Exception as e:
            print(f"Error sending control: {str(e)}")
            return False

class USBManager:
    """Singleton class to manage USB device with CDC and HID interfaces"""
    _instance = None
    
    # Control bit masks for HID media controls
    MUTE =        0b00000001  # Bit 0
    VOL_UP =      0b00000010  # Bit 1
    VOL_DOWN =    0b00000100  # Bit 2
    PLAY_PAUSE =  0b00001000  # Bit 3
    NEXT_TRACK =  0b00010000  # Bit 4
    PREV_TRACK =  0b00100000  # Bit 5
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(USBManager, cls).__new__(cls)
            # Initialize instance attributes
            cls._instance.logger = get_logger()
            cls._instance.initialized = False
            cls._instance.cdc = None
            cls._instance.hid = None
            cls._instance.input_buffer = bytearray()
            cls._instance._last_hid_state = 0
            cls._instance.apps = {}  # Dictionary to store app information
            cls._instance.expected_icons = 0  # Track how many icons we expect
            cls._instance.received_icons = 0  # Track how many icons we've received
            cls._instance.processing_icon = False  # Flag to prevent duplicate icon processing
            cls._instance.ui_manager = None  # Reference to UI manager
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def initialize(self):
        """Initialize USB device with CDC and HID interfaces"""
        try:
            # Reset state
            self.initialized = False
            self.input_buffer = bytearray()
            
            # Create interfaces first without initializing
            self.cdc = CDCInterface()
            self.hid = MediaHIDInterface()
            
            # Initialize CDC with non-blocking timeout
            self.cdc.init(timeout=0)
            
            # Get USB device singleton
            device = usb.device.get()
            
            # Initialize device with both interfaces and keep built-in driver
            # Pass interfaces directly as arguments, not as a keyword
            device.init(self.cdc, self.hid, builtin_driver=True)
            
            # Wait for interfaces to be ready
            timeout = time.ticks_add(time.ticks_ms(), 2000)  # 2 second timeout
            while not (self.cdc.is_open() and self.hid.is_open()):
                if time.ticks_diff(time.ticks_ms(), timeout) >= 0:
                    self.logger.error("Timeout waiting for interfaces")
                    return False
                time.sleep_ms(50)
            
            # Duplicate REPL to new CDC interface for second COM port
            import os
            os.dupterm(self.cdc)
            
            self.logger.info("All interfaces configured successfully")
            self.initialized = True
            self.logger.info("USB device initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize USB device: {str(e)}")
            return False
    
    def read_line(self):
        """Read a line from CDC interface"""
        if not self.initialized or not self.cdc:
            return None
            
        try:
            # Check if data is available
            # CDC read requires max_length parameter
            data = self.cdc.read(64)  # Read up to 64 bytes at a time
            if data:
                # Add to input buffer
                self.input_buffer.extend(data)
                
                # Check for newline
                try:
                    nl_idx = self.input_buffer.index(b'\n'[0])
                    # Extract line and remove from buffer
                    line = bytes(self.input_buffer[:nl_idx]).decode().strip()
                    self.input_buffer = self.input_buffer[nl_idx + 1:]
                    return line
                except ValueError:
                    # No newline found
                    pass
            return None
        except Exception as e:
            self.logger.error(f"Error reading line: {str(e)}")
            return None
    
    def send_message(self, data):
        """Send message through CDC interface"""
        if not self.initialized or not self.cdc:
            self.logger.error("Cannot send message - not initialized")
            return False
            
        try:
            message = json.dumps(data) + '\n'
            # Write to CDC interface
            n = self.cdc.write(message.encode())
            if n > 0:
                self.logger.debug(f"Sent message: {message.strip()}")
                return True
            else:
                self.logger.warning("No bytes sent")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to send message: {str(e)}")
            return False
    
    def send_media_control(self, control, duration_ms=100):
        """Send a media control command with automatic release"""
        if not self.initialized or not self.hid:
            return False
            
        try:
            return self.hid.send_control(control, duration_ms)
        except Exception as e:
            self.logger.error(f"Error sending media control: {str(e)}")
            return False
    
    def is_ready(self):
        """Check if USB device is initialized and ready"""
        return self.initialized and self.cdc and self.hid and self.cdc.is_open() and self.hid.is_open()
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.initialized = False
            self.cdc = None
            self.hid = None
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
    
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
                        self.logger.warning(f"Icon already exists for app: {app_name}")
                    else:
                        self.logger.warning("Invalid icon data request")
            
        except Exception as e:
            self.logger.error(f"Error handling message: {str(e)}") 
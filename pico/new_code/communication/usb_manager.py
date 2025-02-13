import json
import time
import sys
from core.logger import get_logger
import usb.device
from usb.device.cdc import CDCInterface
from usb.device.hid import HIDInterface
from core.config import UIState
import binascii

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
            # Log the control being sent
            print(f"Sending HID control: {control:02x}")
            # Send the control
            self.send_report(bytes([control]))
            time.sleep_ms(duration_ms)
            # Send release
            self.send_report(bytes([0]))
            return True
        except Exception as e:
            print(f"Error sending HID control: {str(e)}")
            return False


class USBManager:
    """Singleton class to manage USB device with CDC and HID interfaces"""
    _instance = None

    # Control bit masks for HID media controls
    MUTE = 0x01      # Bit 0
    VOL_UP = 0x02    # Bit 1
    VOL_DOWN = 0x04  # Bit 2
    PLAY_PAUSE = 0x08  # Bit 3
    NEXT_TRACK = 0x10  # Bit 4
    PREV_TRACK = 0x20  # Bit 5

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
            # Flag to prevent duplicate icon processing
            cls._instance.processing_icon = False
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

            # Get USB device singleton and set descriptors for composite device
            device = usb.device.get()
            device.device_class = 0xEF      # Multi-interface Function
            device.device_subclass = 0x02   # USB Common Sub Class
            device.device_protocol = 0x01   # USB IAD Protocol
            device.max_packet_len = 0x40    # 64 bytes
            device.vid = 0x2E8A  # Raspberry Pi VID
            device.pid = 0x0005  # Your PID
            device.manufacturer = "MicroPython"
            device.product = "Board in FS mode"

            # Initialize device with both interfaces and keep built-in driver
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
            data = self.cdc.read(64)  # Read up to 64 bytes at a time
            if data:
                # Handle different data types
                if isinstance(data, int):
                    self.input_buffer.append(data)
                elif isinstance(data, (bytes, bytearray)):
                    self.input_buffer.extend(data)
                else:
                    self.logger.error(f"Unexpected data type: {type(data)}")
                    return None

                # Check for newline
                try:
                    # Look for newline in buffer
                    for i in range(len(self.input_buffer)):
                        if self.input_buffer[i] == 10:  # 10 is ASCII for newline
                            # Extract line and remove from buffer
                            line = bytes(self.input_buffer[:i]).decode('utf-8').strip()
                            self.input_buffer = self.input_buffer[i + 1:]
                            return line
                except Exception as e:
                    self.logger.error(f"Error processing buffer: {str(e)}")
                    self.input_buffer = bytearray()  # Clear buffer on error
            return None
        except Exception as e:
            self.logger.error(f"Error reading line: {str(e)}")
            return None

    def send_message(self, data, max_retries=3):
        """Send message through CDC interface with retries"""
        if not self.initialized or not self.cdc:
            self.logger.error("Cannot send message - not initialized")
            return False

        for attempt in range(max_retries):
            try:
                message = json.dumps(data) + '\n'
                # Write to CDC interface
                n = self.cdc.write(message.encode())
                if n > 0:
                    self.logger.debug(f"Sent message: {message.strip()}")
                    return True
                else:
                    self.logger.warning(f"No bytes sent (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep_ms(100)  # Small delay before retry
                        continue
                    return False

            except Exception as e:
                self.logger.error(f"Failed to send message (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep_ms(100)  # Small delay before retry
                    continue
                return False
        return False

    def send_media_control(self, control, duration_ms=100):
        """Send a media control command with automatic release"""
        if not self.initialized or not self.hid:
            self.logger.error("Cannot send media control - not initialized")
            return False

        try:
            # Log the control being sent
            self.logger.debug(f"Sending HID control: {control:02x}")  # Changed to debug level
            return self.hid.send_control(control, duration_ms)
        except Exception as e:
            self.logger.error(f"Error sending HID control: {str(e)}")
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
            self.logger.debug(f"Message data: {data}")  # Log full message data

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
                    self.logger.info(
                        f"Processed {len(self.apps)} unique apps from initial config, expecting {self.expected_icons} icons")

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
                self.logger.debug(f"Current processing_icon flag: {self.processing_icon}")
                self.logger.debug(f"Apps in registry: {list(self.apps.keys())}")
                
                if app_name and app_name in self.apps and not self.processing_icon:
                    self.processing_icon = True
                    try:
                        # Send ready for icon data
                        ready_msg = {
                            "type": "ready_for_icon",
                            "app": app_name
                        }
                        if self.send_message(ready_msg):
                            self.logger.info(f"Ready to receive icon for {app_name}")
                        else:
                            self.logger.error(f"Failed to send ready message for {app_name}")
                            self.processing_icon = False
                    except Exception as e:
                        self.logger.error(f"Error preparing for icon: {str(e)}")
                        self.processing_icon = False
                else:
                    if self.processing_icon:
                        self.logger.info(f"Already processing an icon (for previous app), skipping request for {app_name}")
                    elif app_name not in self.apps:
                        self.logger.warning(f"Icon data request for unknown app: {app_name}")
                    else:
                        self.logger.warning(f"Invalid icon data request state for {app_name}")

            elif msg_type == "icon_data_b64":
                app_name = data.get("app")
                b64_data = data.get("data")
                self.logger.debug(f"Processing b64 data for {app_name}, processing_icon flag: {self.processing_icon}")

                if app_name and b64_data and app_name in self.apps:
                    try:
                        if self.handle_icon_data_b64(app_name, b64_data):
                            self.logger.info(f"Successfully processed icon for {app_name}")
                        else:
                            self.logger.error(f"Failed to process icon for {app_name}")
                    finally:
                        self.logger.debug(f"Clearing processing_icon flag for {app_name}")
                        self.processing_icon = False  # Clear processing flag
                else:
                    if not app_name:
                        self.logger.warning("Missing app name in icon data request")
                    elif not b64_data:
                        self.logger.warning(f"Missing base64 data for {app_name}")
                    elif app_name not in self.apps:
                        self.logger.warning(f"Icon data received for unknown app: {app_name}")
                    else:
                        self.logger.warning(f"Invalid icon data received for {app_name}")

            elif msg_type == "init_complete":
                self.logger.info("Initialization complete")
                # Send ready message to start normal operation
                self.send_message({"type": "ready"})
                # Transition to full UI if we have all expected icons
                if self.received_icons == self.expected_icons and self.ui_manager:
                    self.ui_manager.set_state(UIState.FULL_UI)

        except Exception as e:
            self.logger.error(f"Error handling message: {str(e)}")
            if self.processing_icon:
                self.processing_icon = False

    def handle_icon_data_b64(self, app_name, b64_data):
        """Handle base64 encoded icon data"""
        try:
            # Log raw data length for debugging
            self.logger.info(f"Received base64 data for {app_name}, length: {len(b64_data)}")
            
            # Decode base64 data using binascii
            try:
                icon_data = binascii.a2b_base64(b64_data)
                self.logger.info(f"Decoded icon data for {app_name}, size: {len(icon_data)} bytes")
                
                # Print first few bytes for debugging
                debug_bytes = " ".join(f"{b:02x}" for b in icon_data[:16])
                self.logger.debug(f"First 16 bytes: {debug_bytes}")
                
            except Exception as e:
                raise ValueError(f"Failed to decode base64 data: {str(e)}")

            # Verify size is correct (48x48x2 = 4608 bytes)
            if len(icon_data) != 4608:
                raise ValueError(f"Invalid icon size: {len(icon_data)} bytes, expected 4608 bytes")

            # Store the icon data
            try:
                # Log the icon data details
                self.logger.info(f"Storing icon data for {app_name}")
                self.logger.debug(f"Icon data type: {type(icon_data)}")
                
                # Convert to bytes and store
                icon_bytes = bytes(icon_data)
                self.logger.debug(f"Converted to bytes, length: {len(icon_bytes)}")
                
                # Store in apps dictionary
                if app_name not in self.apps:
                    self.apps[app_name] = {}
                self.apps[app_name]["icon"] = icon_bytes
                self.logger.debug(f"Stored icon in apps dictionary for {app_name}")
                
                # Update UI manager's app data if available
                if self.ui_manager:
                    if app_name not in self.ui_manager.apps:
                        self.ui_manager.apps[app_name] = {}
                    self.ui_manager.apps[app_name]["icon"] = icon_bytes
                    self.logger.debug(f"Updated UI manager's icon data for {app_name}")
                    
                self.received_icons += 1
                self.logger.info(f"Successfully stored icon data. Received {self.received_icons}/{self.expected_icons} icons")

                # Send confirmation with retries
                confirm = {
                    "type": "icon_parsed",
                    "app": app_name,
                    "status": "ok"
                }
                if not self.send_message(confirm, max_retries=3):
                    raise ValueError(f"Failed to send confirmation for {app_name}")
                
                return True
                
            except (TypeError, ValueError) as e:
                raise ValueError(f"Failed to store icon data for {app_name}: {str(e)}")
            except Exception as e:
                raise ValueError(f"Unexpected error storing icon data for {app_name}: {str(e)}")
                
        except ValueError as e:
            self.logger.error(f"Icon data validation error for {app_name}: {str(e)}")
            error = {
                "type": "icon_parsed",
                "app": app_name,
                "status": "error",
                "error": str(e)
            }
            self.send_message(error, max_retries=3)
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error processing icon data for {app_name}: {str(e)}")
            error = {
                "type": "icon_parsed",
                "app": app_name,
                "status": "error",
                "error": f"Internal error: {str(e)}"
            }
            self.send_message(error, max_retries=3)
            return False

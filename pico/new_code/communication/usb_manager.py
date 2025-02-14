import json
import time
import sys
from core.logger import get_logger
import usb.device
from usb.device.cdc import CDCInterface
from usb.device.hid import HIDInterface
from core.config import UIState
import binascii
import gc

# For older MicroPython versions that don't have JSONDecodeError in json module
try:
    from json import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError  # Use ValueError as fallback

# Message Types
MSG_HEARTBEAT = "hb"     # Heartbeat
MSG_CONNECT = "conn"     # Connection/handshake
MSG_ICON_REQ = "ireq"    # Icon request
MSG_ICON_TRANSFER = "itr" # Icon transfer
MSG_UPDATE = "upd"       # State update
MSG_ERROR = "err"        # Error message
MSG_ACK = "ack"         # Acknowledgment
MSG_INITIAL_CONFIG = "init"  # Initial configuration
MSG_VOLUME_CMD = "vcmd"  # Volume command acknowledgment

# Expected icon size in bytes (RGB565 format)
ICON_SIZE = 4608  # 48x48x2 bytes
ICON_CACHE_SIZE = 8  # Maximum number of icons to cache
HEARTBEAT_TIMEOUT_MS = 5000  # 5 second timeout for heartbeat

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
            cls._instance.icon_cache = {}  # Separate cache for icons
            cls._instance.icon_cache_order = []  # Track order for LRU cache
            cls._instance.last_heartbeat = 0
            cls._instance.connected = False
            cls._instance.ui_manager = None
            cls._instance.pending_icons = set()  # Track icons that need to be loaded
            cls._instance.initial_config_received = False  # Track if initial config was received
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

            # Initialize CDC with increased timeout for improved read stability
            self.cdc.init(timeout=100)

            # Get USB device singleton and set descriptors for composite device
            device = usb.device.get()
            device.device_class = 0xEF      # Multi-interface Function
            device.device_subclass = 0x02   # USB Common Sub Class
            device.device_protocol = 0x01   # USB IAD Protocol
            device.max_packet_len = 0x40    # 64 bytes
            device.vid = 0x2E8A  # Raspberry Pi VID
            device.pid = 0x0005  # Specific PID
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

    def send_message(self, msg_type, payload=None):
        """Send a message using the lean protocol format"""
        if not self.cdc:
            return False
            
        try:
            message = {
                "t": msg_type,
                "p": payload if payload is not None else {}
            }
            json_str = json.dumps(message)
            if not json_str.endswith('\n'):
                json_str += '\n'
            self.cdc.write(json_str.encode())
            return True
        except Exception as e:
            self.logger.error(f"Send error: {str(e)}")
            return False

    def read_message(self):
        """Read and parse a message in the lean protocol format"""
        if not self.cdc:
            return None, None

        try:
            line = self.read_line()
            if line:
                message = json.loads(line)
                return message.get("t"), message.get("p", {})
            return None, None
        except Exception as e:
            self.logger.error(f"Read error: {str(e)}")
            return None, None

    def _update_icon_cache(self, app_name, icon_data):
        """Update icon cache using LRU policy"""
        try:
            # Remove from cache order if already exists
            if app_name in self.icon_cache_order:
                self.icon_cache_order.remove(app_name)
            
            # Add to front of cache order
            self.icon_cache_order.insert(0, app_name)
            
            # If cache is full, remove least recently used icon
            if len(self.icon_cache_order) > ICON_CACHE_SIZE:
                lru_app = self.icon_cache_order.pop()
                if lru_app in self.icon_cache:
                    del self.icon_cache[lru_app]
                    self.logger.info(f"Removed {lru_app} icon from cache (LRU)")
            
            # Store icon in cache
            self.icon_cache[app_name] = icon_data
            self.logger.info(f"Added {app_name} icon to cache")
            
            # Remove from pending icons if it was pending
            if app_name in self.pending_icons:
                self.pending_icons.remove(app_name)
                self._check_ui_state()
            
            # Run garbage collection after cache update
            gc.collect()
            
        except Exception as e:
            self.logger.error(f"Error updating icon cache: {str(e)}")

    def handle_message(self, msg_type, payload):
        """Handle incoming messages based on type"""
        try:
            if msg_type == MSG_HEARTBEAT:
                self.last_heartbeat = time.ticks_ms()
                self.connected = True
                # Send heartbeat back for bi-directional monitoring
                self.send_message(MSG_HEARTBEAT)
                
            elif msg_type == MSG_CONNECT:
                self.connected = True
                self.send_message(MSG_ACK)
                # Request initial configuration
                self.send_message(MSG_INITIAL_CONFIG)
                
            elif msg_type == MSG_INITIAL_CONFIG:
                # Clear existing state for fresh config
                self.apps.clear()
                self.icon_cache.clear()
                self.icon_cache_order.clear()
                gc.collect()  # Clean up memory
                
                if "apps" in payload:
                    self._handle_apps_update(payload["apps"], is_initial=True)
                self.send_message(MSG_ACK)
                
            elif msg_type == MSG_ICON_TRANSFER:
                if not payload or "n" not in payload or "d" not in payload:
                    self.send_message(MSG_ERROR, {"m": "Invalid icon data"})
                    return
                    
                try:
                    app_name = payload["n"]
                    # Use binascii instead of base64
                    icon_data = binascii.a2b_base64(payload["d"])
                    
                    # Validate icon size
                    if len(icon_data) != ICON_SIZE:
                        self.send_message(MSG_ERROR, {
                            "m": f"Invalid icon size: {len(icon_data)}"
                        })
                        return
                    
                    # Update icon cache
                    self._update_icon_cache(app_name, icon_data)
                    
                    # Update app data and UI
                    if app_name in self.apps:
                        self.apps[app_name]["icon"] = icon_data
                        if self.ui_manager:
                            self.ui_manager.update_app_icon(app_name, icon_data)
                    
                    self.send_message(MSG_ACK)
                    
                except Exception as e:
                    self.send_message(MSG_ERROR, {"m": f"Icon decode error: {str(e)}"})
                    
            elif msg_type == MSG_UPDATE:
                if "apps" in payload:
                    self._handle_apps_update(payload["apps"], is_initial=False)
                if "vol" in payload:
                    self._handle_volume_update(payload["vol"])
                self.send_message(MSG_ACK)
                
            elif msg_type == MSG_VOLUME_CMD:
                # Handle volume command acknowledgment
                if self.ui_manager and "app" in payload and "v" in payload:
                    self.ui_manager.handle_volume_update(payload["app"], payload["v"])
                
        except Exception as e:
            self.logger.error(f"Message handling error: {str(e)}")
            self.send_message(MSG_ERROR, {"m": str(e)})

    def request_icon(self, app_name):
        """Request an icon from the PC"""
        return self.send_message(MSG_ICON_REQ, {"n": app_name})

    def check_connection(self):
        """Check if connection is still alive based on heartbeat"""
        if not self.connected:
            return False
        
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_heartbeat) > HEARTBEAT_TIMEOUT_MS:
            self.connected = False
            self.apps.clear()  # Clear cached state
            self.icon_cache.clear()  # Clear icon cache
            self.icon_cache_order.clear()  # Clear cache order
            self.pending_icons.clear()  # Clear pending icons
            self.initial_config_received = False  # Reset initial config flag
            if self.ui_manager:
                self.ui_manager.set_state(UIState.SIMPLE_MEDIA)
                self.ui_manager.clear_apps()
            gc.collect()  # Clean up memory
            return False
        return True

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
        """Clean up resources and clear caches"""
        try:
            self.initialized = False
            self.apps.clear()
            self.icon_cache.clear()
            self.icon_cache_order.clear()
            self.cdc = None
            self.hid = None
            gc.collect()  # Force garbage collection
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")

    def _handle_apps_update(self, new_apps, is_initial=False):
        """Handle incoming apps update with icon cache management"""
        try:
            self.logger.info("Received apps update")
            
            if not is_initial:
                # Track removed apps to clean cache
                removed_apps = set(self.apps.keys()) - set(new_apps.keys())
                for app_name in removed_apps:
                    if app_name in self.icon_cache:
                        del self.icon_cache[app_name]
                        self.icon_cache_order.remove(app_name)
                        self.logger.info(f"Removed {app_name} icon from cache (app removed)")
            
            # Update apps
            self.apps.update(new_apps)
            
            # Track which icons we need
            self.pending_icons.clear()
            for app_name, app_data in new_apps.items():
                if app_data.get("i", False) and app_name not in self.icon_cache:
                    self.pending_icons.add(app_name)
                    self.request_icon(app_name)
            
            if is_initial:
                self.initial_config_received = True
                self._check_ui_state()
            
            self.logger.info(f"Updated apps: {list(self.apps.keys())}")
            gc.collect()  # Clean up after updates
            
        except Exception as e:
            self.logger.error(f"Error handling apps update: {str(e)}")

    def _handle_volume_update(self, vol):
        """Handle incoming volume update"""
        try:
            self.logger.info(f"Received volume update: {vol}")
            # Implement volume update logic here
        except Exception as e:
            self.logger.error(f"Error handling volume update: {str(e)}")

    def send_heartbeat(self):
        """
        Send a heartbeat message to confirm connection liveness.
        """
        heartbeat_msg = {"type": "heartbeat"}
        return self.send_message(MSG_HEARTBEAT)

    def _check_ui_state(self):
        """Check if conditions are met to switch to full UI"""
        try:
            if (self.ui_manager and self.connected and 
                self.initial_config_received and not self.pending_icons):
                self.logger.info("All conditions met - switching to full UI")
                
                # First update all apps in the UI
                if self.ui_manager:
                    # Set state to SIMPLE_MEDIA while we update
                    self.ui_manager.set_state(UIState.SIMPLE_MEDIA)
                    
                    # Clear and update all apps
                    if hasattr(self.ui_manager, 'clear_apps'):
                        self.ui_manager.clear_apps()
                    
                    # Add all apps with their icons
                    for app_name, app_data in self.apps.items():
                        icon_data = self.icon_cache.get(app_name)
                        if icon_data:
                            self.ui_manager.update_app_icon(app_name, icon_data)
                            # Set volume if available
                            if "v" in app_data:
                                self.ui_manager.handle_volume_update(app_name, app_data["v"])
                
                    # Then switch to full UI mode
                    self.ui_manager.set_state(UIState.FULL_UI)
            else:
                self.logger.info("Conditions for full UI not met yet")
                if self.ui_manager:
                    self.ui_manager.set_state(UIState.SIMPLE_MEDIA)
        except Exception as e:
            self.logger.error(f"Error checking UI state: {str(e)}")
            # On error, stay in SIMPLE_MEDIA mode
            if self.ui_manager:
                self.ui_manager.set_state(UIState.SIMPLE_MEDIA)

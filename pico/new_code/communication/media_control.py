import usb.device
from usb.device.hid import HIDInterface
import time
from core.logger import get_logger

class MediaControlHID:
    """Singleton class to manage HID media controls"""
    _instance = None
    
    @staticmethod
    def get_instance():
        if MediaControlHID._instance is None:
            MediaControlHID._instance = MediaControlHID()
        return MediaControlHID._instance
    
    def __init__(self):
        if MediaControlHID._instance is not None:
            raise Exception("This class is a singleton! Use get_instance() instead.")
        
        self.logger = get_logger()
        self.hid = None
        self.initialized = False
    
    def initialize(self):
        """Initialize HID device"""
        if self.initialized:
            return True
            
        try:
            self.hid = MediaHIDInterface()
            # Initialize USB device with HID interface
            usb_dev = usb.device.get()
            usb_dev.init(self.hid, builtin_driver=True)
            
            # Wait for device to be opened by host
            timeout = 100  # 10 seconds timeout
            while not self.hid.is_open() and timeout > 0:
                time.sleep_ms(100)
                timeout -= 1
            
            if timeout <= 0:
                self.logger.error("Timeout waiting for HID device to be opened")
                return False
                
            self.initialized = True
            self.logger.info("HID device initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing HID device: {str(e)}")
            return False
    
    def send_media_control(self, control, duration_ms=100):
        """Send a media control command with automatic release"""
        if not self.initialized or not self.hid:
            return False
            
        try:
            self.hid.send_control(control)
            time.sleep_ms(duration_ms)
            self.hid.send_control()  # Release
            return True
        except Exception as e:
            self.logger.error(f"Error sending media control: {str(e)}")
            return False
    
    def is_ready(self):
        """Check if HID device is initialized and ready"""
        return self.initialized and self.hid and self.hid.is_open()

class MediaHIDInterface(HIDInterface):
    # Control bit masks
    MUTE =        0b00000001  # Bit 0
    VOL_UP =      0b00000010  # Bit 1
    VOL_DOWN =    0b00000100  # Bit 2
    PLAY_PAUSE =  0b00001000  # Bit 3
    NEXT_TRACK =  0b00010000  # Bit 4
    PREV_TRACK =  0b00100000  # Bit 5

    def __init__(self):
        """Initialize custom HID device"""
        self.logger = get_logger()
        self.logger.info("MediaHIDInterface: Creating new instance")
        super().__init__(
            report_descriptor=self.REPORT_DESCRIPTOR,
            interface_str="MicroPython Media Control",
        )
        self._last_state = 0
        self.logger.info("MediaHIDInterface: Instance created successfully")

    def send_control(self, control=None):
        """Send media control command"""
        if control is None:
            self.send_report(b"\x00")
        else:
            self.send_report(bytes([control & 0x3F]))  # Use bottom 6 bits
            
    # HID Report descriptor for media and volume controls
    REPORT_DESCRIPTOR = bytes([
        0x05, 0x0C,        # Usage Page (Consumer)
        0x09, 0x01,        # Usage (Consumer Control)
        0xA1, 0x01,        # Collection (Application)
        
        # Media and volume controls
        0x15, 0x00,        # Logical Minimum (0)
        0x25, 0x01,        # Logical Maximum (1)
        0x75, 0x01,        # Report Size (1)
        0x95, 0x06,        # Report Count (6) - 6 controls
        
        # Individual button usages
        0x09, 0xE2,        # Usage (Mute)           - bit 0
        0x09, 0xE9,        # Usage (Volume Up)      - bit 1
        0x09, 0xEA,        # Usage (Volume Down)    - bit 2
        0x09, 0xCD,        # Usage (Play/Pause)     - bit 3
        0x09, 0xB5,        # Usage (Next Track)     - bit 4
        0x09, 0xB6,        # Usage (Previous Track) - bit 5
        0x81, 0x02,        # Input (Data, Variable, Absolute)
        
        # Padding
        0x75, 0x02,        # Report Size (2)
        0x95, 0x01,        # Report Count (1)
        0x81, 0x03,        # Input (Constant)
        
        0xC0               # End Collection
    ]) 
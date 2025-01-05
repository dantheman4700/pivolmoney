import usb.device
from usb.device.hid import HIDInterface
import time
from micropython import const

def log(msg):
    """Log message to file"""
    with open('hid.log', 'a') as f:
        f.write(str(msg) + '\n')

class VolumeControlHID(HIDInterface):
    # Control bit masks
    MUTE =        const(0b00000001)  # Bit 0
    VOL_UP =      const(0b00000010)  # Bit 1
    VOL_DOWN =    const(0b00000100)  # Bit 2
    PLAY_PAUSE =  const(0b00001000)  # Bit 3
    NEXT_TRACK =  const(0b00010000)  # Bit 4
    PREV_TRACK =  const(0b00100000)  # Bit 5

    def __init__(self):
        """Initialize custom HID device"""
        log("VolumeControlHID: Creating new instance")
        super().__init__(
            report_descriptor=self.REPORT_DESCRIPTOR,
            interface_str="MicroPython Media Control",
        )
        self._last_state = 0
        log("VolumeControlHID: Instance created successfully")

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

def test_media_controls():
    # Create HID device
    log("Creating HID device...")
    device = VolumeControlHID()
    
    # Initialize USB device
    log("Initializing USB device...")
    usb.device.get().init(device, builtin_driver=True)
    
    # Wait for device to be opened by host
    while not device.is_open():
        time.sleep_ms(100)
    
    log("Device opened by host, starting test...")
    
    while True:
        # Test all controls
        controls = [
            (VolumeControlHID.VOL_UP, "Volume Up"),
            (VolumeControlHID.VOL_DOWN, "Volume Down"),
            (VolumeControlHID.MUTE, "Mute"),
            (VolumeControlHID.PLAY_PAUSE, "Play/Pause"),
            (VolumeControlHID.NEXT_TRACK, "Next Track"),
            (VolumeControlHID.PREV_TRACK, "Previous Track")
        ]
        
        for control, name in controls:
            print(f"Testing {name}...")
            device.send_control(control)
            time.sleep_ms(100)
            device.send_control()  # Release
            time.sleep(1)

if __name__ == "__main__":
    test_media_controls() 
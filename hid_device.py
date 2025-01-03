from micropython import const
import machine
import struct
import time

_EP_IN_FLAG = const(1 << 7)

# USB registers
USB_CTRL = const(0x50110000)        # USB Control register
USB_DEVICE_CLASS = const(0x50110004) # USB Device Class register
USB_EP1_IN_CTRL = const(0x50110088)  # EP1 IN Control register

class HIDDevice:
    def __init__(self, report_descriptor):
        print("Initializing HID device...")
        self.report_descriptor = report_descriptor
        self.report_buffer = bytearray(8)  # Standard report size
        
        print("Switching to HID mode...")
        try:
            # Save original USB configuration
            self._original_class = machine.mem32[USB_DEVICE_CLASS]
            self._original_ctrl = machine.mem32[USB_CTRL]
            
            # Disable USB device
            print("Disabling USB device...")
            machine.mem32[USB_CTRL] &= ~1
            time.sleep_ms(100)  # Give host time to recognize disconnect
            
            # Configure as pure HID device
            print("Setting USB device class to HID...")
            machine.mem32[USB_DEVICE_CLASS] = 0x00000003  # HID Class
            
            # Configure endpoint for HID reports
            print("Configuring HID endpoint...")
            machine.mem32[USB_EP1_IN_CTRL] = 0x00040000  # Set EP1 as interrupt endpoint
            
            # Re-enable USB device
            print("Enabling USB device...")
            machine.mem32[USB_CTRL] |= 1
            print("HID mode enabled")
            
        except Exception as e:
            print(f"Error during initialization: {e}")
            self.cleanup()  # Restore original configuration
            raise
        
    def send_report(self, data):
        """Send a HID report."""
        try:
            # Copy data to report buffer
            for i in range(min(len(data), len(self.report_buffer))):
                self.report_buffer[i] = data[i]
                
            # Write to endpoint 1 (interrupt endpoint)
            addr = 0x50110100 + 8  # EP1 buffer
            machine.mem32[addr] = int.from_bytes(self.report_buffer, 'little')
            machine.mem32[addr + 4] = len(self.report_buffer)
            return True
        except Exception as e:
            print(f"Error sending report: {e}")
            return False
            
    def cleanup(self):
        """Restore original USB configuration."""
        try:
            print("Switching back to serial mode...")
            # Disable USB device
            machine.mem32[USB_CTRL] &= ~1
            time.sleep_ms(100)  # Give host time to recognize disconnect
            
            # Restore original configuration
            machine.mem32[USB_DEVICE_CLASS] = self._original_class
            machine.mem32[USB_CTRL] = self._original_ctrl
            print("Serial mode restored")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")

# Simple gamepad report descriptor
GAMEPAD_REPORT_DESCRIPTOR = bytes([
    0x05, 0x01,  # Usage Page (Generic Desktop)
    0x09, 0x05,  # Usage (Game Pad)
    0xA1, 0x01,  # Collection (Application)
    0x15, 0x00,  # Logical Minimum (0)
    0x25, 0xFF,  # Logical Maximum (255)
    0x75, 0x08,  # Report Size (8)
    0x95, 0x08,  # Report Count (8)
    0x81, 0x02,  # Input (Data, Variable, Absolute)
    0xC0        # End Collection
]) 
from micropython import const
import machine
import struct
import time

class HIDDevice:
    def __init__(self, report_descriptor):
        print("Initializing HID device...")
        self.report_descriptor = report_descriptor
        self.report_buffer = bytearray(8)  # Standard report size
        self.usb_dev = machine.USBDevice()
        
        print("Switching to HID mode...")
        try:
            # Configure USB device
            self.usb_dev.active(False)  # Disable USB to reconfigure
            
            # Configure device with HID interface
            self.usb_dev.config(
                # Device descriptor
                bytes([
                    0x12,   # bLength
                    0x01,   # bDescriptorType (Device)
                    0x00, 0x02,  # bcdUSB (2.0)
                    0x00,   # bDeviceClass (defined at interface level)
                    0x00,   # bDeviceSubClass
                    0x00,   # bDeviceProtocol
                    0x40,   # bMaxPacketSize0 (64 bytes)
                    0x83, 0x04,  # idVendor (0x0483)
                    0x11, 0x57,  # idProduct (0x5711)
                    0x00, 0x01,  # bcdDevice (1.0)
                    0x01,   # iManufacturer (String Index)
                    0x02,   # iProduct (String Index)
                    0x00,   # iSerialNumber (None)
                    0x01    # bNumConfigurations
                ]),
                # Configuration descriptor
                bytes([
                    # Configuration Descriptor
                    0x09,   # bLength
                    0x02,   # bDescriptorType (Configuration)
                    0x22, 0x00,  # wTotalLength (34 bytes)
                    0x01,   # bNumInterfaces
                    0x01,   # bConfigurationValue
                    0x00,   # iConfiguration (no string)
                    0x80,   # bmAttributes (bus powered)
                    0x32,   # bMaxPower (100mA)
                    
                    # Interface Descriptor
                    0x09,   # bLength
                    0x04,   # bDescriptorType (Interface)
                    0x00,   # bInterfaceNumber
                    0x00,   # bAlternateSetting
                    0x01,   # bNumEndpoints
                    0x03,   # bInterfaceClass (HID)
                    0x00,   # bInterfaceSubClass
                    0x00,   # bInterfaceProtocol
                    0x00,   # iInterface (no string)
                    
                    # HID Descriptor
                    0x09,   # bLength
                    0x21,   # bDescriptorType (HID)
                    0x11, 0x01,  # bcdHID (1.11)
                    0x00,   # bCountryCode
                    0x01,   # bNumDescriptors
                    0x22,   # bDescriptorType (Report)
                    len(self.report_descriptor), 0x00,  # wDescriptorLength
                    
                    # Endpoint Descriptor
                    0x07,   # bLength
                    0x05,   # bDescriptorType (Endpoint)
                    0x81,   # bEndpointAddress (IN endpoint 1)
                    0x03,   # bmAttributes (Interrupt)
                    0x08, 0x00,  # wMaxPacketSize (8 bytes)
                    0x0A    # bInterval (10ms)
                ]),
                # String descriptors
                ["Pico", "HID Device"],
                # Callbacks
                self._open_callback,
                self._reset_callback,
                self._control_callback,
                self._transfer_callback
            )
            
            # Enable USB device
            print("Enabling USB device...")
            self.usb_dev.active(True)
            print("HID mode enabled")
            
        except Exception as e:
            print(f"Error during initialization: {e}")
            self.cleanup()
            raise
    
    def _open_callback(self, data):
        """Called when USB interface is opened"""
        print("USB interface opened")
        return True
    
    def _reset_callback(self):
        """Called when USB bus is reset"""
        print("USB bus reset")
        return True
    
    def _control_callback(self, data):
        """Handle USB control requests"""
        try:
            # Parse setup packet
            bmRequestType, bRequest, wValue, wIndex, wLength = struct.unpack("<BBHHH", data[:8])
            
            # Handle HID class-specific requests
            if bmRequestType & 0x60 == 0x20:  # Class request
                if bRequest == 0x0A:  # SET_IDLE
                    return True
                elif bRequest == 0x09:  # SET_REPORT
                    return True
                elif bRequest == 0x01:  # GET_REPORT
                    return self.report_buffer
                elif bRequest == 0x03:  # GET_PROTOCOL
                    return bytes([0])  # Report protocol
            
            # Handle standard requests
            elif bmRequestType & 0x60 == 0x00:  # Standard request
                if bRequest == 0x06:  # GET_DESCRIPTOR
                    desc_type = wValue >> 8
                    if desc_type == 0x22:  # Report descriptor
                        return self.report_descriptor
            
            return None  # Unsupported request
            
        except Exception as e:
            print(f"Error in control callback: {e}")
            return None
    
    def _transfer_callback(self, ep, data, status):
        """Called when USB transfer completes"""
        print(f"Transfer complete: EP{ep}, status={status}")
        return True
        
    def send_report(self, data):
        """Send a HID report."""
        try:
            # Copy data to report buffer
            for i in range(min(len(data), len(self.report_buffer))):
                self.report_buffer[i] = data[i]
            
            # Submit report to endpoint 1
            return self.usb_dev.submit(1, self.report_buffer)
            
        except Exception as e:
            print(f"Error sending report: {e}")
            return False
            
    def cleanup(self):
        """Restore original USB configuration."""
        try:
            print("Switching back to serial mode...")
            self.usb_dev.active(False)  # Disable custom USB device
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
from machine import USBDevice
import struct
import time

# Global variable for log initialization state
_log_initialized = False

def log(message):
    """Write log message to file, overwriting if it's the first message"""
    global _log_initialized
    # Use 'w' for first write, 'a' for subsequent writes
    mode = 'w' if not _log_initialized else 'a'
    timestamp = time.ticks_ms()
    try:
        with open('hid_log.txt', mode) as f:
            f.write(f"[{timestamp}] {message}\n")
            f.flush()  # Force write to file
    except Exception as e:
        with open('hid_log.txt', 'a') as f:
            f.write(f"[{timestamp}] Log error: {str(e)}\n")
            f.flush()
    _log_initialized = True

class CustomHIDDevice:
    # USB Device Descriptor
    DEVICE_DESCRIPTOR = bytes([
        0x12,   # bLength
        0x01,   # bDescriptorType (Device)
        0x00, 0x02,  # bcdUSB 2.0
        0x00,   # bDeviceClass (Use class from Interface)
        0x00,   # bDeviceSubClass
        0x00,   # bDeviceProtocol
        0x40,   # bMaxPacketSize0 64
        0x8A, 0x2E,  # idVendor (Raspberry Pi)
        0x05, 0x00,  # idProduct (Custom HID)
        0x00, 0x01,  # bcdDevice 1.0
        0x01,   # iManufacturer (String Index)
        0x02,   # iProduct (String Index)
        0x00,   # iSerialNumber (String Index)
        0x01    # bNumConfigurations 1
    ])

    # HID Report Descriptor for custom device with Feature reports
    REPORT_DESCRIPTOR = bytes([
        0x06, 0x00, 0xFF,  # Usage Page (Vendor Defined)
        0x09, 0x01,        # Usage (Vendor Usage 1)
        0xA1, 0x01,        # Collection (Application)
        
        # Input report - for volume updates from host
        0x09, 0x02,        # Usage (Vendor Usage 2)
        0x15, 0x00,        # Logical Minimum (0)
        0x26, 0xFF, 0x00,  # Logical Maximum (255)
        0x75, 0x08,        # Report Size (8)
        0x95, 0x08,        # Report Count (8)
        0x81, 0x02,        # Input (Data, Variable, Absolute)
        
        # Output report - for sending commands to host
        0x09, 0x03,        # Usage (Vendor Usage 3)
        0x15, 0x00,        # Logical Minimum (0)
        0x26, 0xFF, 0x00,  # Logical Maximum (255)
        0x75, 0x08,        # Report Size (8)
        0x95, 0x08,        # Report Count (8)
        0x91, 0x02,        # Output (Data, Variable, Absolute)
        
        # Feature report - for configuration/settings
        0x09, 0x04,        # Usage (Vendor Usage 4)
        0x15, 0x00,        # Logical Minimum (0)
        0x26, 0xFF, 0x00,  # Logical Maximum (255)
        0x75, 0x08,        # Report Size (8)
        0x95, 0x08,        # Report Count (8)
        0xB1, 0x02,        # Feature (Data, Variable, Absolute)
        
        0xC0               # End Collection
    ])

    # Configuration Descriptor
    CONFIG_DESCRIPTOR = bytes([
        # Configuration Descriptor
        0x09,   # bLength
        0x02,   # bDescriptorType (Configuration)
        0x29, 0x00,  # wTotalLength (41 bytes)
        0x01,   # bNumInterfaces
        0x01,   # bConfigurationValue
        0x00,   # iConfiguration (String Index)
        0xE0,   # bmAttributes (Self Powered + Remote Wakeup)
        0x32,   # bMaxPower 100mA

        # Interface Descriptor
        0x09,   # bLength
        0x04,   # bDescriptorType (Interface)
        0x00,   # bInterfaceNumber 0
        0x00,   # bAlternateSetting
        0x02,   # bNumEndpoints 2 (IN and OUT)
        0x03,   # bInterfaceClass (HID)
        0x00,   # bInterfaceSubClass
        0x00,   # bInterfaceProtocol
        0x00,   # iInterface (String Index)

        # HID Descriptor
        0x09,   # bLength
        0x21,   # bDescriptorType (HID)
        0x11, 0x01,  # bcdHID 1.11
        0x00,   # bCountryCode
        0x01,   # bNumDescriptors
        0x22,   # bDescriptorType[0] (Report)
        0x3F, 0x00,  # wDescriptorLength[0] 63

        # Endpoint Descriptor (IN)
        0x07,   # bLength
        0x05,   # bDescriptorType (Endpoint)
        0x81,   # bEndpointAddress (IN)
        0x03,   # bmAttributes (Interrupt)
        0x08, 0x00,  # wMaxPacketSize 8
        0x0A,   # bInterval 10ms

        # Endpoint Descriptor (OUT)
        0x07,   # bLength
        0x05,   # bDescriptorType (Endpoint)
        0x01,   # bEndpointAddress (OUT)
        0x03,   # bmAttributes (Interrupt)
        0x08, 0x00,  # wMaxPacketSize 8
        0x0A    # bInterval 10ms
    ])

    def __init__(self):
        """Initialize custom HID device"""
        log("CustomHIDDevice: Creating new instance")
        self.usb_dev = USBDevice()
        self.in_buffer = bytearray(8)
        self.out_buffer = bytearray(8)
        self.in_endpoint = 0x81
        self.out_endpoint = 0x01
        self._device_configured = False
        log("CustomHIDDevice: Instance created successfully")

    def init(self):
        """Initialize the USB device"""
        try:
            log("USB Init: Starting initialization")
            # First, deactivate any current USB configuration
            if self.usb_dev.active():
                log("USB Init: Deactivating current USB configuration")
                self.usb_dev.active(False)
                time.sleep(1)
            
            # Set built-in driver to none
            log("USB Init: Setting built-in driver to NONE")
            self.usb_dev.builtin_driver = USBDevice.BUILTIN_NONE
            
            # String descriptors with proper USB string descriptor format
            log("USB Init: Creating string descriptors")
            str_descriptors = {
                0: bytes([0x04, 0x03, 0x09, 0x04]),  # Language ID (English)
                1: self._create_string_descriptor("Raspberry Pi"),
                2: self._create_string_descriptor("Volume Control Device")
            }
            
            # Configure the USB device
            log("USB Init: Configuring USB device with descriptors")
            self.usb_dev.config(
                desc_dev=self.DEVICE_DESCRIPTOR,
                desc_cfg=self.CONFIG_DESCRIPTOR,
                desc_strs=str_descriptors,
                xfer_cb=self._xfer_callback,
                control_xfer_cb=self._control_callback,
                open_itf_cb=self._interface_callback
            )
            
            log("USB Init: Configuration complete, activating device")
            self.usb_dev.active(True)
            
            # Wait for device to be configured
            timeout = 100  # 10 seconds
            log("USB Init: Waiting for device configuration")
            while timeout > 0:
                if self._device_configured:
                    log("USB Init: Device configured successfully")
                    break
                time.sleep(0.1)
                timeout -= 1
                if timeout % 10 == 0:  # Log every second
                    log(f"USB Init: Still waiting for configuration, {timeout/10} seconds remaining")
            
            if timeout <= 0:
                log("USB Init: Timeout waiting for device configuration")
                return False
                
            log("USB Init: Starting data reception")
            # Start listening for incoming data
            self._start_receive()
            
            log("USB Init: HID device fully initialized and ready")
            return True
            
        except Exception as e:
            log(f"USB Init Error: Failed to initialize USB device: {str(e)}")
            log(f"USB Init Error type: {type(e)}")
            import sys
            sys.print_exception(e)
            return False

    def _create_string_descriptor(self, string):
        """Create a proper USB string descriptor"""
        # Convert string to UTF-16LE bytes
        string_bytes = string.encode('utf-16-le')
        length = len(string_bytes) + 2
        # Create descriptor (length + type + UTF-16LE string)
        descriptor = bytearray(length)
        descriptor[0] = length
        descriptor[1] = 0x03  # String descriptor type
        descriptor[2:] = string_bytes
        return bytes(descriptor)

    def _start_receive(self):
        """Start listening for incoming data"""
        try:
            if self.usb_dev and self.usb_dev.active():
                log("Starting receive on OUT endpoint")
                self.usb_dev.submit_xfer(self.out_endpoint, self.out_buffer)
            else:
                log("Warning: Cannot start receive - device not active")
        except Exception as e:
            log(f"Error starting receive: {str(e)}")

    def _xfer_callback(self, ep, result, xferred_bytes):
        """Handle transfer completion"""
        if result:
            if ep == self.out_endpoint:  # Data received from host
                data = [hex(x) for x in self.out_buffer[:xferred_bytes]]
                log(f"Received data from host on EP {hex(ep)}: {data}")
                # Echo received data back to host
                self.send_data(self.out_buffer[:xferred_bytes])
                # Start listening for next packet
                self._start_receive()
            else:  # Data sent to host
                log(f"Data sent to host on EP {hex(ep)}: {xferred_bytes} bytes")
        else:
            log(f"Transfer failed on EP {hex(ep)}")
            if ep == self.out_endpoint:
                log("Restarting receive after failure")
                self._start_receive()

    def _control_callback(self, stage, data):
        """Handle USB control transfers"""
        try:
            if stage == 1:  # SETUP stage
                setup_data = bytes(data)
                if len(setup_data) >= 8:
                    bmRequestType = setup_data[0]
                    bRequest = setup_data[1]
                    wValue = setup_data[2] | (setup_data[3] << 8)
                    wIndex = setup_data[4] | (setup_data[5] << 8)
                    log(f"Control Setup: Type={hex(bmRequestType)} Request={hex(bRequest)} Value={hex(wValue)} Index={hex(wIndex)}")
                    
                    # Handle GET_DESCRIPTOR requests
                    if bmRequestType == 0x81 and bRequest == 0x06:
                        descriptor_type = wValue >> 8
                        descriptor_index = wValue & 0xFF
                        
                        if descriptor_type == 0x22:  # Report descriptor
                            log("Sending HID Report Descriptor")
                            return self.REPORT_DESCRIPTOR
                        elif descriptor_type == 0x03:  # String descriptor
                            log(f"Sending String Descriptor {descriptor_index}")
                            if descriptor_index == 0:
                                return bytes([0x04, 0x03, 0x09, 0x04])
                            elif descriptor_index == 1:
                                return self._create_string_descriptor("Raspberry Pi")
                            elif descriptor_index == 2:
                                return self._create_string_descriptor("Volume Control Device")
                    
                    # Handle SET_CONFIGURATION
                    elif bmRequestType == 0x00 and bRequest == 0x09:
                        log("Set Configuration request")
                        self._device_configured = True
                        
            return True
        except Exception as e:
            log(f"Control callback error: {e}")
            return False

    def _interface_callback(self, descriptor):
        """Called when interface is opened by host"""
        log("Interface opened by host")
        self._device_configured = True
        return True

    def deinit(self):
        """Deinitialize the USB device"""
        try:
            log("USB Deinit: Starting deinitialization")
            if self.usb_dev.active():
                log("USB Deinit: Deactivating device")
                self.usb_dev.active(False)
                time.sleep(1)
            log("USB Deinit: Setting built-in driver back to DEFAULT")
            self.usb_dev.builtin_driver = USBDevice.BUILTIN_DEFAULT
            log("USB Deinit: Reactivating with default driver")
            self.usb_dev.active(True)
            log("USB Deinit: Device successfully deinitialized")
            return True
        except Exception as e:
            log(f"USB Deinit Error: Failed to deinitialize USB device: {str(e)}")
            log(f"USB Deinit Error type: {type(e)}")
            import sys
            sys.print_exception(e)
            return False

    def send_data(self, data):
        """Send data to host"""
        try:
            if len(data) > 8:
                data = data[:8]  # Truncate to 8 bytes
            
            # Check USB device state
            if not self.usb_dev:
                log("Error: USB device not initialized")
                return False
                
            if not self.usb_dev.active():
                log("Error: USB device not active")
                return False
                
            if not self._device_configured:
                log("Error: Device not configured")
                return False
                
            log(f"USB state before send - Active: {self.usb_dev.active()}, Configured: {self._device_configured}")
            self.in_buffer[:len(data)] = data
            log(f"Sending data to host: {[hex(x) for x in self.in_buffer]}")
            
            # Try to submit transfer
            try:
                result = self.usb_dev.submit_xfer(self.in_endpoint, self.in_buffer)
                log(f"Send result: {result}")
                return result
            except OSError as e:
                log(f"OSError during submit_xfer: {e.args[0]}")
                # Try to recover USB state
                if e.args[0] == 16:  # Device busy
                    log("Device busy, checking USB state...")
                    if self.usb_dev.active():
                        log("USB still active, might need reset")
                    else:
                        log("USB no longer active")
                raise
                
        except Exception as e:
            log(f"Error in send_data: {str(e)}")
            return False 
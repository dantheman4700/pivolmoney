import rp2
import time
import machine
from hid_device import HIDDevice, GAMEPAD_REPORT_DESCRIPTOR

print("Starting HID Test...")
print("This will switch the Pico to HID mode")
print("Press BOOTSEL button once to exit and return to serial mode")
print("Note: Thonny will disconnect while in HID mode")

hid = None  # Initialize to None so we can check in finally block

try:
    print("Switching to HID mode in 3 seconds...")
    print("(Disconnect from Thonny expected)")
    time.sleep(3)
    
    # Initialize HID device
    hid = HIDDevice(GAMEPAD_REPORT_DESCRIPTOR)
    
    counter = 0
    last_report_time = 0
    last_button_state = False
    
    while True:
        current_time = time.ticks_ms()
        
        # Check BOOTSEL button - detect press and release
        button_state = rp2.bootsel_button()
        if button_state and not last_button_state:  # Button just pressed
            break  # Exit loop to cleanup
        last_button_state = button_state
        
        # Send a test report every second
        if time.ticks_diff(current_time, last_report_time) >= 1000:
            counter = (counter + 1) % 256
            report = bytearray(8)  # Create 8-byte report
            report[0] = counter    # Set first byte to counter value
            try:
                hid.send_report(report)
            except Exception as e:
                print(f"Error sending report: {e}")
            last_report_time = current_time
        
        time.sleep_ms(10)

except Exception as e:
    print(f"Error in main loop: {e}")

finally:
    # Clean exit
    if hid:
        hid.cleanup()  # This will restore serial mode
    # Give time for USB to reset before script ends
    time.sleep(1) 
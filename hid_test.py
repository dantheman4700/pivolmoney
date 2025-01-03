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
    print("Creating HID device...")
    hid = HIDDevice(GAMEPAD_REPORT_DESCRIPTOR)
    print("HID device created successfully")
    
    counter = 0
    last_report_time = 0
    last_button_state = False
    
    print("Entering main loop...")
    while True:
        current_time = time.ticks_ms()
        
        # Check BOOTSEL button - detect press and release
        button_state = machine.Pin(23, machine.Pin.IN, machine.Pin.PULL_DOWN).value()
        if button_state and not last_button_state:  # Button just pressed
            print("BOOTSEL pressed, exiting...")
            break  # Exit loop to cleanup
        last_button_state = button_state
        
        # Send a test report every second
        if time.ticks_diff(current_time, last_report_time) >= 1000:
            counter = (counter + 1) % 256
            report = bytearray(8)  # Create 8-byte report
            report[0] = counter    # Set first byte to counter value
            print(f"Sending report: counter = {counter}")
            if hid.send_report(report):
                print("Report sent successfully")
            else:
                print("Failed to send report")
            last_report_time = current_time
        
        # Small delay to prevent tight loop
        time.sleep_ms(1)

except Exception as e:
    print(f"Error in main loop: {e}")
    import sys
    sys.print_exception(e)  # Print full traceback

finally:
    # Clean exit
    if hid:
        print("Cleaning up USB...")
        try:
            hid.cleanup()  # This will restore serial mode
            print("Cleanup complete")
        except Exception as e:
            print(f"Error during cleanup: {e}")
            import sys
            sys.print_exception(e)
    time.sleep(1)  # Give time for USB to reset 
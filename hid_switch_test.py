import time
import rp2
from machine import reset
from HID_new import CustomHIDDevice, log

try:
    # Start with a fresh log file
    log("=== Starting HID Test with USB State Logging ===")
    log("This script will switch the Pico to Custom HID mode.")
    log("Press BOOTSEL button to exit and reboot.")
    
    # Add delay for Wireshark to start capturing
    log("Waiting 5 seconds before starting (time to start Wireshark capture)...")
    time.sleep(5)
    
    # Create device with detailed logging
    log("Creating HID device...")
    device = CustomHIDDevice()

    log("=== Starting USB Mode Switch ===")
    log("Current mode: CDC/Serial (COM)")
    log("Initializing HID mode...")
    
    if not device.init():
        log("Failed to initialize HID device!")
        reset()  # Normal reboot on failure

    log("=== HID Device Initialized ===")
    log("Waiting 2 seconds for USB enumeration to complete...")
    time.sleep(2)  # Give time for USB enumeration

    log("=== Attempting HID Data Transfer ===")
    # Send a single test pattern with detailed logging
    test_pattern = bytes([0x01, 0x02, 0x03, 0x04])
    
    try:
        log(f"Preparing to send test pattern: {[hex(x) for x in test_pattern]}")
        log("Adding pre-transfer delay of 100ms...")
        time.sleep(0.1)
        
        log("Initiating HID report transfer...")
        result = device.send_data(test_pattern)
        
        if result:
            log("HID report transfer successful")
            log("Waiting 1 second before entering button monitoring...")
            time.sleep(1)
        else:
            log("HID report transfer failed")
            reset()  # Normal reboot on failure
            
    except Exception as e:
        log(f"Error during HID transfer: {str(e)}")
        log("Exception details:", str(type(e)))
        reset()  # Normal reboot on error

    log("=== Entering Button Monitor Mode ===")
    log("Waiting for BOOTSEL button press to exit...")

    # Initial button state
    log("Reading initial button state...")
    last_state = rp2.bootsel_button()
    log(f"Initial button state: {'Pressed' if last_state else 'Released'}")
    
    debounce_time = 50  # 50ms debounce
    last_change = time.ticks_ms()
    loop_count = 0
    
    log("=== Button Monitor Active ===")
    
    while True:
        try:
            current_state = rp2.bootsel_button()
            current_time = time.ticks_ms()
            
            # Log every 2000th iteration to reduce spam
            loop_count += 1
            if loop_count % 2000 == 0:
                log(f"Monitor active - iteration {loop_count}")
            
            # Only process state changes after debounce period
            if current_state != last_state and time.ticks_diff(current_time, last_change) > debounce_time:
                log(f"Button state changed - BOOTSEL {'pressed' if current_state else 'released'}")
                if current_state:  # Button pressed
                    log("=== BOOTSEL Pressed - Initiating Normal Reboot ===")
                    log("Waiting 3500ms before reboot...")
                    time.sleep(3.5)  # Wait 3500ms before rebooting
                    reset()  # Normal reboot when button is pressed
                last_state = current_state
                last_change = current_time
            
            time.sleep_ms(10)
        except Exception as e:
            log(f"Error in button monitor: {str(e)}")
            reset()  # Normal reboot on error

except Exception as e:
    log(f"Critical error: {str(e)}")
    reset()  # Normal reboot on error
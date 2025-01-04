import time
import rp2
from machine import bootloader
from HID_new import CustomHIDDevice, log

try:
    # Start with a fresh log file
    log("Starting HID switch test...")
    log("This script will switch the Pico to Custom HID mode.")
    log("Press BOOTSEL button at any time to reboot to bootloader.")
    log("The device will echo back any data it receives.")
    log("")
    log("Starting in 3 seconds...")
    time.sleep(3)

    # Create device
    log("Creating HID device...")
    device = CustomHIDDevice()

    log("Switching to HID mode...")
    if not device.init():
        log("Failed to initialize device!")
        raise SystemExit

    log("Device initialized, sending test sequence...")

    # Send a sequence of test patterns
    test_patterns = [
        bytes([0x01, 0x02, 0x03, 0x04]),  # Simple sequence
        bytes([0xFF, 0x00, 0xFF, 0x00]),  # Alternating pattern
        bytes([0x55, 0xAA, 0x55, 0xAA])   # Another pattern
    ]

    try:
        log("Starting test pattern sequence...")
        for i, pattern in enumerate(test_patterns, 1):
            log(f"\nSending test pattern {i}: {[hex(x) for x in pattern]}")
            device.send_data(pattern)
            time.sleep(1)  # Wait between patterns
        log("Test pattern sequence completed successfully")
    except Exception as e:
        log(f"Error during test patterns: {str(e)}")
        log(f"Error type: {type(e)}")
        import sys
        sys.print_exception(e)
        raise

    log("About to send completion messages...")
    log("\nTest patterns sent. Now waiting for any incoming data.")
    log("The device will echo back any data it receives.")
    log("Press BOOTSEL to reboot to bootloader, or Ctrl+C to exit...")

    log("About to enter button monitoring section...")
    log("=== ENTERING BUTTON MONITORING SECTION ===")
    log("Starting BOOTSEL button test...")

    try:
        # Initial state
        log("About to read initial button state...")
        last_state = rp2.bootsel_button()
        log(f"Initial button state: {'Pressed' if last_state else 'Released'}")
        
        debounce_time = 50  # 50ms debounce
        last_change = time.ticks_ms()
        loop_count = 0
        
        log("=== STARTING BUTTON MONITORING LOOP ===")
        log("About to enter main monitoring loop...")
        
        while True:
            try:
                if loop_count == 0:
                    log("First iteration of monitoring loop")
                
                current_state = rp2.bootsel_button()
                current_time = time.ticks_ms()
                
                # Log every 500th iteration to verify loop is running
                loop_count += 1
                if loop_count % 500 == 0:
                    log(f"Loop iteration {loop_count}, raw button state: {current_state}")
                
                # Only process state changes after debounce period
                if current_state != last_state and time.ticks_diff(current_time, last_change) > debounce_time:
                    log(f"Button state changed - BOOTSEL button {'pressed' if current_state else 'released'}")
                    if current_state:  # Button pressed
                        log("BOOTSEL pressed - Starting reboot sequence...")
                        log("Deinitializing USB...")
                        device.deinit()  # Clean up USB
                        log("Waiting for cleanup...")
                        time.sleep(0.5)  # Give it time to clean up
                        log("Rebooting to bootloader...")
                        machine.bootloader()  # Reboot to bootloader
                    last_state = current_state
                    last_change = current_time
                
                # Print debug info every 2 seconds
                if time.ticks_ms() % 2000 < 100:
                    log(f"Debug - Current state: {'Pressed' if current_state else 'Released'}")
                
                time.sleep_ms(10)
            except Exception as e:
                log(f"Error in monitoring loop iteration: {str(e)}")
                log(f"Loop error type: {type(e)}")
                raise  # Re-raise to outer try/except
                
    except KeyboardInterrupt:
        log("\nExiting due to KeyboardInterrupt...")
    except Exception as e:
        log(f"Error in button monitoring section: {str(e)}")
        log(f"Error type: {type(e)}")
        import sys
        sys.print_exception(e)

except Exception as e:
    log(f"Error in main script: {str(e)}")
    log(f"Error type: {type(e)}")
    import sys
    sys.print_exception(e)
finally:
    log("Entering finally block...")
    try:
        # Switch back to CDC mode
        log("Attempting to switch back to CDC mode...")
        device.deinit()
        log("CDC mode restored")
    except Exception as e:
        log(f"Error during cleanup: {str(e)}")

log("Test complete! You can reconnect in Thonny now.")
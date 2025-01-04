import time
import rp2
from machine import bootloader
from HID_new import CustomHIDDevice, log

# Start with a fresh log file
log("Starting HID switch test...")
log("This script will switch the Pico to Custom HID mode.")
log("Press BOOTSEL button at any time to reboot to bootloader.")
log("The device will echo back any data it receives.")
log("")
log("Starting in 3 seconds...")
time.sleep(3)

# Create device
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

for i, pattern in enumerate(test_patterns, 1):
    log(f"\nSending test pattern {i}: {[hex(x) for x in pattern]}")
    device.send_data(pattern)
    time.sleep(1)  # Wait between patterns

log("\nTest patterns sent. Now waiting for any incoming data.")
log("The device will echo back any data it receives.")
log("Press BOOTSEL to reboot to bootloader, or Ctrl+C to exit...")

try:
    # Initial state
    last_state = rp2.bootsel_button()
    log(f"Initial state: {'Pressed' if last_state else 'Released'}")
    
    debounce_time = 50  # 50ms debounce
    last_change = time.ticks_ms()
    
    while True:
        current_state = rp2.bootsel_button()
        current_time = time.ticks_ms()
        
        # Only process state changes after debounce period
        if current_state != last_state and time.ticks_diff(current_time, last_change) > debounce_time:
            log(f"BOOTSEL button {'pressed' if current_state else 'released'}")
            if current_state:  # Button pressed
                log("\nBOOTSEL button pressed, rebooting to bootloader...")
                device.deinit()  # Clean up USB
                time.sleep(0.5)  # Give it time to clean up
                machine.bootloader()  # Reboot to bootloader
            last_state = current_state
            last_change = current_time
        
        # Print debug info every 2 seconds
        if time.ticks_ms() % 2000 < 100:
            log(f"Debug - Current state: {'Pressed' if current_state else 'Released'}")
        
        time.sleep_ms(10)
except KeyboardInterrupt:
    log("\nExiting...")

# Switch back to CDC mode
log("Switching back to CDC mode...")
device.deinit()

log("Test complete! You can reconnect in Thonny now.") 
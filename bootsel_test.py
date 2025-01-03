import rp2
import time

print("Starting BOOTSEL button test...")
print("Press the BOOTSEL button to see the state change")
print("Press Ctrl+C to exit")

# Initial state
last_state = rp2.bootsel_button()
print(f"Initial state: {'Pressed' if last_state else 'Released'}")

debounce_time = 50  # 50ms debounce
last_change = time.ticks_ms()

while True:
    current_state = rp2.bootsel_button()
    current_time = time.ticks_ms()
    
    # Only process state changes after debounce period
    if current_state != last_state and time.ticks_diff(current_time, last_change) > debounce_time:
        print(f"BOOTSEL button {'pressed' if current_state else 'released'}")
        last_state = current_state
        last_change = current_time
    
    # Print debug info every 2 seconds
    if time.ticks_ms() % 2000 < 100:
        print(f"Debug - Current state: {'Pressed' if current_state else 'Released'}")
    
    time.sleep_ms(10) 
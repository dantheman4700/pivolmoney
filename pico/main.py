from app_volume_serial import AppVolumeController, log_to_file
import time
import rp2

def main():
    log_to_file("Starting main.py - waiting for BOOTSEL")
    
    # Initial state
    last_state = rp2.bootsel_button()
    debounce_time = 50  # 50ms debounce
    last_change = time.ticks_ms()
    
    while True:
        current_state = rp2.bootsel_button()
        current_time = time.ticks_ms()
        
        # Only process state changes after debounce period
        if current_state != last_state and time.ticks_diff(current_time, last_change) > debounce_time:
            if current_state:  # Button pressed
                log_to_file("BOOTSEL pressed - Starting volume control")
                break
            last_state = current_state
            last_change = current_time
            
        time.sleep_ms(10)
    
    # Initialize volume control after BOOTSEL press
    controller = AppVolumeController()
    log_to_file("Volume control started - CDC interface active")
    
    while True:
        controller.update()
        time.sleep(0.01)

if __name__ == "__main__":
    main() 

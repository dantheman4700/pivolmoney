import sys
import time
from app_volume_serial import AppVolumeController, log_to_file

def debug_print(message):
    """Print debug messages to stderr to avoid interfering with serial JSON"""
    print(message, file=sys.stderr)

def run_tests(controller):
    """Run a series of tests to verify functionality"""
    log_to_file("Starting test sequence")
    debug_print("Running tests - check serial.log for details")
    
    # Initial delay to ensure serial is ready
    time.sleep(1)
    
    test_steps = [
        ("Request initial app list", lambda: controller.request_app_list()),
        ("Wait for response", lambda: time.sleep(0.5)),
        ("Set system volume to 25%", lambda: controller.set_app_volume("System", 25)),
        ("Wait for response", lambda: time.sleep(0.5)),
        ("Toggle system mute ON", lambda: controller.toggle_app_mute()),
        ("Wait for response", lambda: time.sleep(0.5)),
        ("Set system volume to 50%", lambda: controller.set_app_volume("System", 50)),
        ("Wait for response", lambda: time.sleep(0.5)),
        ("Toggle system mute OFF", lambda: controller.toggle_app_mute()),
        ("Wait for response", lambda: time.sleep(0.5)),
        ("Request updated app list", lambda: controller.request_app_list()),
    ]
    
    for step_name, step_func in test_steps:
        log_to_file(f"Starting test step: {step_name}")
        debug_print(f"Testing: {step_name}")
        
        try:
            step_func()
            log_to_file(f"Executed test step: {step_name}")
        except Exception as e:
            log_to_file(f"Error in test step {step_name}: {e}")
            debug_print(f"Test error: {e}")
            continue
            
        # Process any responses
        for i in range(5):  # Check for responses multiple times
            try:
                controller.update()
                time.sleep(0.2)
            except Exception as e:
                log_to_file(f"Error processing response in step {step_name}: {e}")
    
    log_to_file("Test sequence completed")
    debug_print("Tests completed - entering normal operation")

def main():
    try:
        debug_print("Starting volume control service...")
        
        # Initialize controller
        controller = AppVolumeController()
        if not controller.init_serial():
            log_to_file("Failed to initialize serial")
            debug_print("Failed to initialize serial - check serial.log")
            return
        
        log_to_file("Serial communication initialized")
        debug_print("Serial communication initialized")
        
        # Small delay to ensure serial is ready
        time.sleep(0.5)
        
        # Run initial tests
        run_tests(controller)
        
        log_to_file("Starting main loop")
        debug_print("Volume control running - check serial.log for details")
        
        # Main loop
        while True:
            controller.update()
            time.sleep(0.1)  # Small delay to prevent CPU hogging
                
    except Exception as e:
        log_to_file(f"Main loop error: {e}")
        debug_print(f"Error: {e}")
        
    finally:
        log_to_file("Main loop terminated")
        debug_print("Volume control stopped")

if __name__ == "__main__":
    main() 
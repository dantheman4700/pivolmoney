import gc
import time
import rp2
import sys
from machine import Pin, Timer
from core.logger import get_logger
from core.config import UIState, DISPLAY_WIDTH, DISPLAY_HEIGHT
from ui.ui_manager import UIManager
from communication.communication import CommunicationManager
from communication.media_control import MediaHIDInterface

logger = get_logger()
ui_manager = None
comm_manager = None

def handle_interrupt(cleanup=True):
    """Handle keyboard interrupt gracefully"""
    global ui_manager, comm_manager
    if cleanup:
        logger.info("Received interrupt - cleaning up")
        if ui_manager:
            ui_manager.cleanup()
        if comm_manager:
            comm_manager.cleanup()
    sys.exit(0)

def wait_for_bootsel():
    """Wait for BOOTSEL button press with interrupt handling"""
    logger.info("Starting BOOTSEL button test...")
    
    # Initial state
    last_state = rp2.bootsel_button()
    debounce_time = 50  # 50ms debounce
    last_change = time.ticks_ms()
    
    try:
        while True:
            current_state = rp2.bootsel_button()
            current_time = time.ticks_ms()
            
            # Only process state changes after debounce period
            if current_state != last_state and time.ticks_diff(current_time, last_change) > debounce_time:
                if current_state:  # Button pressed
                    logger.info("BOOTSEL pressed - Starting volume control")
                    return True
                last_state = current_state
                last_change = current_time
                
            time.sleep_ms(10)
    except KeyboardInterrupt:
        logger.info("Interrupted during BOOTSEL wait")
        return False

def handle_media_control(action):
    """Handle media control actions"""
    logger.info(f"Media control action: {action}")
    if comm_manager and comm_manager.media_control:
        try:
            logger.debug(f"HID interface ready: {comm_manager.media_control.is_ready()}")
            if action == 'play':
                success = comm_manager.media_control.send_media_control(MediaHIDInterface.PLAY_PAUSE)
                logger.info(f"PLAY_PAUSE command {'sent' if success else 'failed'}")
            elif action == 'prev':
                success = comm_manager.media_control.send_media_control(MediaHIDInterface.PREV_TRACK)
                logger.info(f"PREV_TRACK command {'sent' if success else 'failed'}")
            elif action == 'next':
                success = comm_manager.media_control.send_media_control(MediaHIDInterface.NEXT_TRACK)
                logger.info(f"NEXT_TRACK command {'sent' if success else 'failed'}")
            elif action == 'mute':
                success = comm_manager.media_control.send_media_control(MediaHIDInterface.MUTE)
                logger.info(f"MUTE command {'sent' if success else 'failed'}")
            return success
        except Exception as e:
            logger.error(f"Error in media control: {str(e)}")
            logger.error(f"HID state - initialized: {comm_manager.media_control.initialized}, hid: {comm_manager.media_control.hid is not None}")
    else:
        logger.error("Media control not available - comm_manager or media_control is None")
    return False

def handle_touch(action, app_name=None):
    """Handle touch events"""
    if action in ['play', 'prev', 'next', 'mute']:
        handle_media_control(action)
    elif action == 'app_selected' and app_name:
        logger.info(f"App selected: {app_name}")
        # Handle app selection
        pass

def main():
    global ui_manager, comm_manager
    logger.info("Starting application")
    
    try:
        # Wait for BOOTSEL or interrupt
        if not wait_for_bootsel():
            logger.info("Exiting due to interrupt during startup")
            return
            
        # Initialize UI manager first
        ui_manager = UIManager()
        if not ui_manager.initialize_hardware():
            logger.error("Failed to initialize UI")
            raise Exception("UI initialization failed")
        
        # Initialize communication manager
        comm_manager = CommunicationManager()
        if not comm_manager.initialize():
            logger.error("Failed to initialize communication")
            raise Exception("Communication initialization failed")
        
        # Register touch callback
        ui_manager.register_touch_callback(handle_touch)
        
        # Set initial state to simple media after everything is initialized
        ui_manager.set_state(UIState.SIMPLE_MEDIA)
        
        logger.info("Hardware initialized - starting main loop")
        
        # Main loop with interrupt handling
        while True:
            try:
                # Update communication
                comm_manager.update()
                
                # Update UI
                ui_manager.update()
                
                # Run garbage collection
                gc.collect()
                
                # Small delay to prevent tight loop
                time.sleep_ms(10)
                
            except KeyboardInterrupt:
                logger.info("Received interrupt in main loop")
                handle_interrupt()
                break
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                time.sleep(1)  # Delay before retry
                
    except KeyboardInterrupt:
        handle_interrupt()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    finally:
        handle_interrupt(cleanup=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        handle_interrupt()
    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}") 
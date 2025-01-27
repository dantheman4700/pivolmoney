import gc
import time
import sys
from machine import Pin, Timer, reset
from core.logger import get_logger
from core.config import (
    UIState, DISPLAY_WIDTH, DISPLAY_HEIGHT,
    PIN_ROT_SW  # Add rotary switch pin
)
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

def wait_for_button():
    """Wait for rotary encoder button press with interrupt handling"""
    logger.info("Waiting for rotary button press to start...")
    
    try:
        # Initialize rotary button with pull-up
        button = Pin(PIN_ROT_SW, Pin.IN, Pin.PULL_UP)
        
        # Initial state
        last_state = button.value()
        debounce_time = 50  # 50ms debounce
        last_change = time.ticks_ms()
        
        while True:
            current_state = button.value()
            current_time = time.ticks_ms()
            
            # Only process state changes after debounce period
            if current_state != last_state and time.ticks_diff(current_time, last_change) > debounce_time:
                if current_state == 0:  # Button pressed (active low with pull-up)
                    logger.info("Rotary button pressed - Starting volume control")
                    return True
                last_state = current_state
                last_change = current_time
                
            time.sleep_ms(10)
    except KeyboardInterrupt:
        logger.info("Interrupted during button wait")
        return False
    except Exception as e:
        logger.error(f"Error in button detection: {str(e)}")
        return False

def handle_media_control(action):
    """Handle media control actions"""
    logger.info(f"Media control action: {action}")
    if comm_manager and comm_manager.media_control:
        try:
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
    return False

def handle_touch(action, app_name=None):
    """Handle touch events"""
    if action in ['play', 'prev', 'next', 'mute']:
        handle_media_control(action)
    elif action == 'app_selected' and app_name:
        logger.info(f"App selected: {app_name}")
        # Get current volume for the app
        if comm_manager and app_name in comm_manager.apps:
            volume = comm_manager.apps[app_name].get("volume", 50)
            # Update encoder value to match current volume
            if ui_manager and ui_manager.encoder:
                ui_manager.encoder.set_value(volume)

def handle_encoder(action, app_name=None, value=None):
    """Handle encoder events"""
    logger.info(f"Encoder event: {action} for {app_name} value={value}")
    if not comm_manager:
        return
        
    try:
        if action == 'volume_change' and app_name:
            # Send volume change command
            command = {
                "type": "set_volume",
                "app": app_name,
                "volume": value
            }
            comm_manager.send_message(command)
            
        elif action == 'toggle_mute' and app_name:
            # Send mute toggle command
            command = {
                "type": "toggle_mute",
                "app": app_name
            }
            comm_manager.send_message(command)
            
    except Exception as e:
        logger.error(f"Error handling encoder event: {str(e)}")

def main():
    global ui_manager, comm_manager
    logger.info("Starting application")
    
    try:
        # Wait for rotary button press or interrupt
        if not wait_for_button():
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
        
        # Register callbacks
        ui_manager.register_touch_callback(handle_touch)
        ui_manager.register_encoder_callback(handle_encoder)
        
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
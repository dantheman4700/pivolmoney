import gc
import time
import sys
import json
from machine import Pin, Timer, reset
from core.logger import get_logger
from core.config import (
    UIState, DISPLAY_WIDTH, DISPLAY_HEIGHT,
    PIN_ROT_SW  # Add rotary switch pin
)
from ui.ui_manager import UIManager
from communication.usb_manager import USBManager

logger = get_logger()
ui_manager = None
usb_manager = None

def handle_interrupt(cleanup=True):
    """Handle keyboard interrupt gracefully"""
    global ui_manager, usb_manager
    if cleanup:
        logger.info("Received interrupt - cleaning up")
        if ui_manager:
            ui_manager.cleanup()
        if usb_manager:
            usb_manager.cleanup()
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
    if usb_manager and usb_manager.is_ready():
        try:
            if action == 'play':
                success = usb_manager.send_media_control(USBManager.PLAY_PAUSE)
                logger.info(f"PLAY_PAUSE command {'sent' if success else 'failed'}")
            elif action == 'prev':
                success = usb_manager.send_media_control(USBManager.PREV_TRACK)
                logger.info(f"PREV_TRACK command {'sent' if success else 'failed'}")
            elif action == 'next':
                success = usb_manager.send_media_control(USBManager.NEXT_TRACK)
                logger.info(f"NEXT_TRACK command {'sent' if success else 'failed'}")
            elif action == 'mute':
                success = usb_manager.send_media_control(USBManager.MUTE)
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
        if usb_manager and app_name in usb_manager.apps:
            volume = usb_manager.apps[app_name].get("volume", 50)
            # Update encoder value to match current volume
            if ui_manager and ui_manager.encoder:
                ui_manager.encoder.set_value(volume)

def main():
    """Main application entry point"""
    global ui_manager, usb_manager
    
    try:
        # Initialize USB manager first
        usb_manager = USBManager()  # Create instance
        usb_manager = USBManager.get_instance()  # Get singleton instance
        
        # Initialize UI manager
        ui_manager = UIManager()  # Create instance
        ui_manager = UIManager.get_instance()  # Get singleton instance
        
        # Initialize USB device first
        if not usb_manager.initialize():
            logger.error("Failed to initialize USB device")
            handle_interrupt(cleanup=True)
            return
            
        # Then initialize UI hardware
        if not ui_manager.initialize_hardware():
            logger.error("Failed to initialize UI")
            handle_interrupt(cleanup=True)
            return
            
        # Set UI state to simple media controls
        ui_manager.set_state(UIState.SIMPLE_MEDIA)
        
        # Set up UI manager's touch callback
        ui_manager.touch_callback = handle_touch
        
        # Main loop
        while True:
            # Process any incoming messages
            line = usb_manager.read_line()
            if line:
                try:
                    data = json.loads(line)
                    usb_manager.handle_message(data)
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
            
            # Let the system breathe
            time.sleep_ms(10)
            
    except KeyboardInterrupt:
        handle_interrupt()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        handle_interrupt()

if __name__ == "__main__":
    try:
        # Wait for rotary button press to start
        if wait_for_button():
            main()
        else:
            handle_interrupt(cleanup=False)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        handle_interrupt() 
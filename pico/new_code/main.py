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
                # Button pressed (active low with pull-up)
                if current_state == 0:
                    logger.info(
                        "Rotary button pressed - Starting volume control")
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
    if usb_manager and usb_manager.is_ready():
        try:
            if action == 'play':
                return usb_manager.send_media_control(USBManager.PLAY_PAUSE)
            elif action == 'prev':
                return usb_manager.send_media_control(USBManager.PREV_TRACK)
            elif action == 'next':
                return usb_manager.send_media_control(USBManager.NEXT_TRACK)
            elif action == 'mute':
                return usb_manager.send_media_control(USBManager.MUTE)
            elif action == 'vol_up':
                return usb_manager.send_media_control(USBManager.VOL_UP)
            elif action == 'vol_down':
                return usb_manager.send_media_control(USBManager.VOL_DOWN)
            return False
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


def handle_encoder_callback(action, *args):
    """Handle encoder callbacks"""
    try:
        logger.info(f"Encoder callback: {action} {args}")
        if action == 'volume_change' and len(args) >= 2:
            app_name = args[0]
            volume = args[1]
            logger.info(f"Sending volume change: {app_name} = {volume}")
            if usb_manager and usb_manager.is_ready():
                usb_manager.send_volume_command(app_name, volume)
        elif action == 'master_vol_up':
            logger.info("Master volume up")
            if usb_manager and usb_manager.is_ready():
                current_vol = usb_manager.apps.get("Master", {}).get("volume", 50)
                usb_manager.send_volume_command("Master", min(100, current_vol + 5))
        elif action == 'master_vol_down':
            logger.info("Master volume down")
            if usb_manager and usb_manager.is_ready():
                current_vol = usb_manager.apps.get("Master", {}).get("volume", 50)
                usb_manager.send_volume_command("Master", max(0, current_vol - 5))
    except Exception as e:
        logger.error(f"Error in encoder callback: {str(e)}")


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

        # Connect managers to each other
        usb_manager.ui_manager = ui_manager
        ui_manager.usb_manager = usb_manager

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

        # Set UI state to simple media controls and set up callbacks
        ui_manager.set_state(UIState.SIMPLE_MEDIA)
        ui_manager.touch_callback = handle_touch
        ui_manager.encoder_callback = handle_encoder_callback  # Updated to use new callback

        # Main loop
        while True:
            # Process any incoming messages
            line = usb_manager.read_line()
            if line:
                try:
                    data = json.loads(line)
                    # Extract message type and payload from data
                    msg_type = data.get("t")
                    payload = data.get("p", {})
                    usb_manager.handle_message(msg_type, payload)
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")

            # Process UI events (touch and encoder)
            if ui_manager:
                ui_manager.update()

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

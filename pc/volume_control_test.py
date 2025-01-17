import psutil
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioSessionControl2
import logging
import time
import json
import sys
from comtypes import CLSCTX_ALL, CoCreateInstance, CoInitialize, CoUninitialize

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

def get_process_name_without_exe(name):
    """Remove .exe from process name for better matching"""
    return name.lower().replace('.exe', '')

def get_audio_sessions():
    """Get all audio sessions with their current volume levels"""
    sessions = AudioUtilities.GetAllSessions()
    session_info = []
    
    for session in sessions:
        try:
            if session.Process and session.Process.name():
                volume = session.SimpleAudioVolume
                vol_level = volume.GetMasterVolume()
                muted = volume.GetMute()
                
                # Get process info
                process_name = session.Process.name()
                pid = session.Process.pid
                
                info = {
                    "name": process_name,
                    "pid": pid,
                    "volume": int(vol_level * 100),
                    "muted": muted
                }
                session_info.append(info)
                logger.info(f"Found session: {process_name} (PID: {pid}) - Volume: {info['volume']}% - Muted: {muted}")
        except Exception as e:
            logger.error(f"Error getting session info: {e}")
    
    return session_info

def set_volume(process_name, volume_level):
    """Set volume for a specific application
    Args:
        process_name (str): Name of the process (with or without .exe)
        volume_level (int): Volume level (0-100)
    Returns:
        tuple: (success, current_volume)
    """
    try:
        # Handle master volume separately
        if process_name.lower() == "master":
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(ISimpleAudioVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(ISimpleAudioVolume)
            volume.SetMasterVolume(volume_level / 100, None)
            current_vol = int(volume.GetMasterVolume() * 100)
            logger.info(f"Set master volume to {current_vol}%")
            return True, current_vol

        target_name = get_process_name_without_exe(process_name)
        sessions = AudioUtilities.GetAllSessions()
        
        for session in sessions:
            try:
                if session.Process and session.Process.name():
                    current_name = get_process_name_without_exe(session.Process.name())
                    if current_name == target_name:
                        volume = session.SimpleAudioVolume
                        volume.SetMasterVolume(volume_level / 100, None)
                        current_vol = int(volume.GetMasterVolume() * 100)
                        logger.info(f"Set volume for {process_name} to {current_vol}%")
                        return True, current_vol
            except Exception as e:
                logger.error(f"Error setting volume for session: {e}")
                
        logger.warning(f"Process {process_name} not found")
        return False, None
        
    except Exception as e:
        logger.error(f"Error in set_volume: {e}")
        return False, None

def toggle_mute(process_name):
    """Toggle mute state for a specific application"""
    try:
        # Handle master volume separately
        if process_name.lower() == "master":
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(ISimpleAudioVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(ISimpleAudioVolume)
            current_mute = volume.GetMute()
            volume.SetMute(not current_mute, None)
            logger.info(f"Toggled master mute to {not current_mute}")
            return True

        target_name = get_process_name_without_exe(process_name)
        sessions = AudioUtilities.GetAllSessions()
        
        for session in sessions:
            try:
                if session.Process and session.Process.name():
                    current_name = get_process_name_without_exe(session.Process.name())
                    if current_name == target_name:
                        volume = session.SimpleAudioVolume
                        current_mute = volume.GetMute()
                        volume.SetMute(not current_mute, None)
                        logger.info(f"Toggled mute for {process_name} to {not current_mute}")
                        return True
            except Exception as e:
                logger.error(f"Error toggling mute for session: {e}")
                
        logger.warning(f"Process {process_name} not found")
        return False
        
    except Exception as e:
        logger.error(f"Error in toggle_mute: {e}")
        return False

def handle_command(command):
    """Handle incoming commands from Pico"""
    try:
        cmd_type = command.get("type")
        
        if cmd_type == "set_volume":
            app_name = command.get("app")
            volume = command.get("volume")
            
            if app_name is None or volume is None:
                logger.error("Invalid set_volume command: missing app or volume")
                return
                
            success, current_vol = set_volume(app_name, volume)
            if success:
                # Send volume update confirmation
                response = {
                    "type": "volume_update",
                    "app": app_name,
                    "volume": current_vol
                }
                print(json.dumps(response))
                
        elif cmd_type == "toggle_mute":
            app_name = command.get("app")
            if app_name is None:
                logger.error("Invalid toggle_mute command: missing app")
                return
                
            if toggle_mute(app_name):
                # Get updated mute state
                sessions = get_audio_sessions()
                for session in sessions:
                    if get_process_name_without_exe(session["name"]) == get_process_name_without_exe(app_name):
                        response = {
                            "type": "mute_update",
                            "app": app_name,
                            "muted": session["muted"]
                        }
                        print(json.dumps(response))
                        break
                        
    except Exception as e:
        logger.error(f"Error handling command: {e}")

def test_volume_control():
    """Interactive test for volume control"""
    try:
        CoInitialize()  # Initialize COM
        
        print("\nVolume Control Test")
        print("==================")
        print("1. List audio sessions")
        print("2. Set volume for app")
        print("3. Toggle mute for app")
        print("4. Monitor volume changes")
        print("5. Exit")
        
        while True:
            try:
                # Check for incoming commands from Pico
                if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                    line = sys.stdin.readline().strip()
                    if line:
                        try:
                            command = json.loads(line)
                            handle_command(command)
                        except json.JSONDecodeError:
                            logger.error(f"Invalid JSON command: {line}")
                
                choice = input("\nEnter choice (1-5): ")
                
                if choice == "1":
                    sessions = get_audio_sessions()
                    
                elif choice == "2":
                    app_name = input("Enter app name (or 'Master' for system volume): ")
                    volume = int(input("Enter volume (0-100): "))
                    set_volume(app_name, volume)
                    
                elif choice == "3":
                    app_name = input("Enter app name (or 'Master' for system volume): ")
                    toggle_mute(app_name)
                    
                elif choice == "4":
                    print("Monitoring volume changes (Ctrl+C to stop)...")
                    last_volumes = {}
                    try:
                        while True:
                            sessions = get_audio_sessions()
                            current_volumes = {s["name"]: s["volume"] for s in sessions}
                            
                            # Check for changes
                            for name, volume in current_volumes.items():
                                if name not in last_volumes or last_volumes[name] != volume:
                                    logger.info(f"Volume changed - {name}: {volume}%")
                            
                            last_volumes = current_volumes
                            time.sleep(0.1)
                    except KeyboardInterrupt:
                        print("\nStopped monitoring")
                        
                elif choice == "5":
                    break
                    
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                
    except Exception as e:
        logger.error(f"Error in test_volume_control: {e}")
    finally:
        CoUninitialize()  # Clean up COM

if __name__ == "__main__":
    logger.info("Starting volume control test")
    test_volume_control() 
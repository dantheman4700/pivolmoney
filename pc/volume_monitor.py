from icon_handler import IconHandler
import serial
import json
import time
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
import serial.tools.list_ports
import sys
import base64
from serial_manager import (
    SerialManager, MSG_HEARTBEAT, MSG_CONNECT, MSG_ICON_REQ,
    MSG_ICON_TRANSFER, MSG_UPDATE, MSG_ERROR, MSG_ACK,
    MSG_INITIAL_CONFIG, MSG_VOLUME_CMD
)

class VolumeMonitor:
    def __init__(self):
        self.serial_manager = None
        self.connected = False
        self.initialized = False
        self.last_app_list = {}
        self.update_interval = 1.0
        self.last_update = 0
        self.icon_handler = IconHandler()
        self.last_heartbeat = 0
        self.heartbeat_interval = 1.0  # Send heartbeat every second
        self.update_debounce = 0.1  # 100ms debounce for updates
        self.last_state_update = 0
        print("VolumeMonitor initialized")
        
    def find_pico_com_port(self):
        """Find the COM port for the Pico device"""
        # Don't search if already connected
        if self.connected and self.initialized and self.serial_manager:
            return True
            
        ports = list(serial.tools.list_ports.comports())
        pico_ports = []
        
        for port in ports:
            if "VID:PID=2E8A:0005" in port.hwid:
                pico_ports.append(port.device)
        
        if pico_ports:
            pico_ports.sort(reverse=True)
            
            for port in pico_ports:
                print(f"Attempting connection on {port}")
                self.serial_manager = SerialManager(port)
                if self.try_connect():
                    print(f"Successfully connected on {port}")
                    return True
            
            print("Failed to connect to Pico")
            return False
        
        print("No Pico device found")
        return False
        
    def try_connect(self):
        """Try to connect and establish handshake"""
        try:
            # Don't attempt to connect if already connected
            if self.connected and self.initialized:
                return True
                
            # Send connection message
            if self.serial_manager.send_message(MSG_CONNECT):
                # Wait for acknowledgment and initial config request
                start_time = time.time()
                while time.time() - start_time < 5:  # 5 second timeout
                    msg_type, payload = self.serial_manager.read_message()
                    if msg_type == MSG_ACK:
                        self.connected = True
                        self.last_heartbeat = time.time()
                        print("Received connection acknowledgment")
                        
                    elif msg_type == MSG_INITIAL_CONFIG and self.connected:
                        print("Received initial config request")
                        # Send initial configuration
                        if self.send_initial_config():
                            self.initialized = True
                            print("Initial configuration sent successfully")
                            return True
                    time.sleep(0.1)
            
            if not self.initialized:
                print("Connection attempt failed")
                self.disconnect()
                return False
            
            return self.initialized
            
        except Exception as e:
            print(f"Connection error: {e}")
            self.disconnect()
            return False
            
    def disconnect(self):
        """Safely disconnect from the device"""
        self.connected = False
        self.initialized = False
        if self.serial_manager:
            self.serial_manager.close()
            self.serial_manager = None
        self.icon_handler.clear_cache()
            
    def send_initial_config(self):
        """Send initial configuration to Pico"""
        try:
            app_volumes, _ = self.get_application_volumes()
            
            # Convert to lean format
            lean_apps = {}
            for app in app_volumes:
                lean_apps[app["name"]] = {
                    "v": app["volume"],  # Short key for volume
                    "m": app["muted"],   # Short key for muted
                    "i": app["has_icon"] # Short key for has_icon
                }
            
            return self.serial_manager.send_message(MSG_INITIAL_CONFIG, {
                "apps": lean_apps
            })
        except Exception as e:
            print(f"Error sending initial config: {e}")
            return False

    def send_app_update(self, app_volumes):
        """Send app update using lean protocol"""
        try:
            # Debounce updates
            current_time = time.time()
            if current_time - self.last_state_update < self.update_debounce:
                return True
                
            # Convert to lean format and compare with last state
            lean_apps = {}
            for app in app_volumes:
                lean_apps[app["name"]] = {
                    "v": app["volume"],  # Short key for volume
                    "m": app["muted"],   # Short key for muted
                    "i": app["has_icon"] # Short key for has_icon
                }
            
            # Only send update if apps have changed
            if lean_apps != self.last_app_list:
                success = self.serial_manager.send_message(MSG_UPDATE, {
                    "apps": lean_apps
                })
                
                if success:
                    self.last_state_update = current_time
                    self.last_app_list = lean_apps.copy()  # Use copy to avoid reference issues
                
                return success
            
            return True
            
        except Exception as e:
            print(f"Error sending app update: {e}")
            return False

    def handle_message(self, msg_type, payload):
        """Handle incoming messages using lean protocol"""
        try:
            if msg_type == MSG_ICON_REQ:
                app_name = payload.get("n")  # Short key for name
                if app_name:
                    # Get the process ID for the app
                    pid = None
                    for session in AudioUtilities.GetAllSessions():
                        if session.Process and session.Process.name() == app_name:
                            pid = session.Process.pid
                            break
                    
                    # Get icon using the proper method
                    icon_data = self.icon_handler.get_icon_for_app(app_name, pid)
                    if not icon_data:
                        icon_data = self.icon_handler.get_default_icon()
                    if icon_data:
                        self.serial_manager.send_icon(app_name, icon_data)
                        
            elif msg_type == MSG_HEARTBEAT:
                # Respond to heartbeat for bi-directional monitoring
                self.serial_manager.send_heartbeat()
                
            elif msg_type == "vol":  # Volume command from Pico
                app_name = payload.get("app")
                direction = payload.get("d")  # 1 for up, 0 for down
                print(f"Received volume {direction and 'up' or 'down'} command for {app_name}")  # Debug print
                
                if app_name and direction is not None:
                    success = False
                    current_volume = None
                    
                    if app_name == "Master":
                        current_volume = self.get_master_volume()
                    else:
                        # Use the same method as get_application_volumes
                        sessions = AudioUtilities.GetAllSessions()
                        seen_apps = set()  # Track seen apps to handle duplicates
                        for session in sessions:
                            if session.Process and session.Process.name() == app_name:
                                volume_interface = session.SimpleAudioVolume
                                current_volume = int(volume_interface.GetMasterVolume() * 100)
                                break
                    
                    # Only proceed if we got a valid volume
                    if current_volume is not None:
                        # Adjust volume by 2% up or down
                        new_volume = max(0, min(100, current_volume + (2 if direction else -2)))
                        print(f"Adjusting {app_name} volume from {current_volume} to {new_volume}")  # Debug print
                        
                        if app_name == "Master":
                            success = self.set_master_volume(new_volume)
                        else:
                            success = self.set_app_volume(app_name, new_volume)
                        
                        if success:
                            print(f"Successfully adjusted volume for {app_name}")  # Debug print
                            # Send volume command acknowledgment with new volume
                            self.serial_manager.send_volume_ack(app_name, new_volume)
                            
                            # Get current app volumes and send update
                            app_volumes, _ = self.get_application_volumes()
                            self.send_app_update(app_volumes)
                        else:
                            print(f"Failed to adjust volume for {app_name}")  # Debug print
                    else:
                        print(f"Could not get current volume for {app_name}")  # Debug print

        except Exception as e:
            print(f"Error handling message: {e}")
            
    def update(self):
        """Main update loop with lean protocol"""
        try:
            # Check connection health first
            if not self.serial_manager or not self.serial_manager.check_connection():
                print("Connection lost or not established")
                self.disconnect()
                if not self.connect():
                    time.sleep(1)
                    return
                
            # Check for incoming messages
            msg_type, payload = self.serial_manager.read_message()
            if msg_type:
                self.handle_message(msg_type, payload)
                
            current_time = time.time()
            
            # Send heartbeat
            if current_time - self.last_heartbeat >= self.heartbeat_interval:
                if not self.serial_manager.send_heartbeat():
                    print("Failed to send heartbeat")
                    self.disconnect()
                    return
                self.last_heartbeat = current_time
                    
            # Check for app changes
            if current_time - self.last_update >= self.update_interval:
                app_volumes, icons = self.get_application_volumes()
                
                # Send update if needed
                if self.send_app_update(app_volumes):
                    self.last_update = current_time
                
            time.sleep(0.01)
            
        except Exception as e:
            print(f"Update error: {e}")
            self.disconnect()

    def get_application_volumes(self):
        """Get list of applications and their volumes"""
        sessions = AudioUtilities.GetAllSessions()
        app_volumes = []
        icons_to_send = []
        seen_apps = set()
        
        # Add master volume first
        master_vol = self.get_master_volume()
        app_volumes.append({
            "name": "Master",
            "volume": master_vol,
            "muted": False,
            "has_icon": False
        })
        
        for session in sessions:
            try:
                if session.Process and session.Process.name():
                    volume = session.SimpleAudioVolume
                    process_name = session.Process.name()
                    pid = session.Process.pid
                    
                    if process_name in seen_apps:
                        continue
                    seen_apps.add(process_name)
                    
                    icon_data = self.icon_handler.get_icon_for_app(process_name, pid)
                    
                    app_volumes.append({
                        "name": process_name,
                        "volume": int(volume.GetMasterVolume() * 100),
                        "muted": volume.GetMute(),
                        "has_icon": icon_data is not None
                    })
                    
                    if icon_data:
                        icons_to_send.append({
                            "name": process_name,
                            "icon": icon_data
                        })
                        
            except:
                continue
                
        return app_volumes, icons_to_send

    def connect(self):
        """Connect to the Pico device"""
        # Don't attempt to connect if already connected and initialized
        if self.connected and self.initialized and self.serial_manager:
            return True
            
        print("Attempting to connect...")
        return self.find_pico_com_port()

    def set_master_volume(self, volume_percent):
        """Set Windows master volume"""
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            
            # Convert percentage to scalar
            volume_scalar = max(0.0, min(1.0, volume_percent / 100.0))
            volume.SetMasterVolumeLevelScalar(volume_scalar, None)
            return True
        except Exception as e:
            print(f"Error setting master volume: {e}")
            return False

    def set_app_volume(self, app_name, volume_percent):
        """Set volume for a specific app"""
        try:
            print(f"Setting {app_name} volume to {volume_percent}%")  # Debug log
            sessions = AudioUtilities.GetAllSessions()
            found = False
            for session in sessions:
                if session.Process and session.Process.name() == app_name:
                    volume_interface = session.SimpleAudioVolume
                    # Get current volume before change
                    current_vol = int(volume_interface.GetMasterVolume() * 100)
                    print(f"Current volume before change: {current_vol}%")  # Debug log
                    
                    # Convert percentage to scalar (ensure proper conversion)
                    volume_scalar = max(0.0, min(1.0, float(volume_percent) / 100.0))
                    print(f"Setting volume scalar to: {volume_scalar}")  # Debug log
                    
                    # Set the volume
                    volume_interface.SetMasterVolume(volume_scalar, None)
                    
                    # Verify the change
                    new_vol = int(volume_interface.GetMasterVolume() * 100)
                    print(f"Volume after change: {new_vol}%")  # Debug log
                    
                    found = True
                    break
            
            if not found:
                print(f"No audio session found for {app_name}")
                return False
                
            return True
        except Exception as e:
            print(f"Error setting app volume: {e}")
            return False

    def get_master_volume(self):
        """Get Windows master volume"""
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            
            # Convert from scalar to percentage
            current_vol = volume.GetMasterVolumeLevelScalar()
            return int(current_vol * 100)
        except Exception as e:
            print(f"Error getting master volume: {e}")
            return 0

    def update_master_volume(self):
        """Update master volume in app list and send update"""
        master_vol = self.get_master_volume()
        app_volumes, _ = self.get_application_volumes()
        
        # Send update
        self.send_app_update("Master")

def main():
    monitor = VolumeMonitor()
    print("Volume Monitor starting...")
    
    try:
        while True:
            try:
                monitor.update()
            except KeyboardInterrupt:
                print("Shutting down...")
                monitor.disconnect()
                break
            except Exception as e:
                print(f"Main loop error: {e}")
                time.sleep(1)
    finally:
        monitor.disconnect()
        print("Volume Monitor stopped")

if __name__ == "__main__":
    main()

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
            # Send connection message
            if self.serial_manager.send_message(MSG_CONNECT):
                # Wait for acknowledgment and initial config request
                start_time = time.time()
                while time.time() - start_time < 5:  # 5 second timeout
                    msg_type, payload = self.serial_manager.read_message()
                    if msg_type == MSG_ACK:
                        self.connected = True
                        self.last_heartbeat = time.time()
                    elif msg_type == MSG_INITIAL_CONFIG and self.connected:
                        # Send initial configuration
                        if self.send_initial_config():
                            self.initialized = True
                            return True
                    time.sleep(0.1)
            
            self.disconnect()
            return False
            
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
                    self.last_app_list = lean_apps
                
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
                    icon_data = self.icon_handler.get_window_icon(app_name)
                    if not icon_data:
                        icon_data = self.icon_handler.get_default_icon()
                    if icon_data:
                        self.serial_manager.send_icon(app_name, icon_data)
                        
            elif msg_type == MSG_HEARTBEAT:
                # Respond to heartbeat for bi-directional monitoring
                self.serial_manager.send_heartbeat()
                
        except Exception as e:
            print(f"Error handling message: {e}")
            
    def update(self):
        """Main update loop with lean protocol"""
        if not self.connected:
            if not self.connect():
                time.sleep(1)
                return
                
        try:
            # Check connection health
            if not self.serial_manager.check_connection():
                print("Connection lost - disconnecting")
                self.disconnect()
                return
                
            # Check for incoming messages
            msg_type, payload = self.serial_manager.read_message()
            if msg_type:
                self.handle_message(msg_type, payload)
                
            current_time = time.time()
            
            # Send heartbeat
            if current_time - self.last_heartbeat >= self.heartbeat_interval:
                if self.serial_manager.send_heartbeat():
                    self.last_heartbeat = current_time
                else:
                    self.disconnect()
                    return
                    
            # Check for app changes
            if current_time - self.last_update >= self.update_interval:
                app_volumes, icons = self.get_application_volumes()
                
                # Convert to dict for easier comparison
                current_apps = {app["name"]: app for app in app_volumes}
                
                # Check for any changes in volume or mute state only
                # Ignore icon state changes to prevent icon request loops
                has_changes = False
                if len(current_apps) != len(self.last_app_list):
                    has_changes = True
                else:
                    for app_name, app_data in current_apps.items():
                        if app_name not in self.last_app_list:
                            has_changes = True
                            break
                        last_app = self.last_app_list[app_name]
                        if (app_data["volume"] != last_app.get("volume") or 
                            app_data["muted"] != last_app.get("muted")):
                            has_changes = True
                            break
                
                if has_changes:
                    if self.send_app_update(app_volumes):
                        self.last_app_list = current_apps
                    else:
                        self.disconnect()
                        return
                        
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
        print("Attempting to connect...")
        return self.find_pico_com_port()

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

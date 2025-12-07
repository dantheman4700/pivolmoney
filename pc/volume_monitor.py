import argparse
import base64
import json
import sys
import time

import serial
import serial.tools.list_ports
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume

from icon_handler import IconHandler
from serial_manager import (
    SerialManager, MSG_HEARTBEAT, MSG_CONNECT, MSG_ICON_REQ,
    MSG_ICON_TRANSFER, MSG_UPDATE, MSG_ERROR, MSG_ACK,
    MSG_INITIAL_CONFIG, MSG_VOLUME_CMD
)
from serial_tap import SerialTapServer


def parse_args():
    parser = argparse.ArgumentParser(description="PC host for the volume panel Pico")
    parser.add_argument(
        "--serial-tap-port",
        type=int,
        default=None,
        help="Expose the raw serial stream on this TCP port for debugging.",
    )
    parser.add_argument(
        "--serial-tap-host",
        default="127.0.0.1",
        help="Interface for the tap server (default: 127.0.0.1).",
    )
    return parser.parse_args()


class VolumeMonitor:
    def __init__(self, serial_tap=None):
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
        self.serial_tap = serial_tap
        print("VolumeMonitor initialized")
        
    def find_pico_com_port(self):
        """Find the COM port for the ESP32-S3 device"""
        # Don't search if already connected
        if self.connected and self.initialized and self.serial_manager:
            return True
            
        ports = list(serial.tools.list_ports.comports())
        esp32_ports = []
        
        for port in ports:
            # Check for Silicon Labs CP210x (ESP32-S3)
            # Also check for CH340 as backup (common ESP32 UART chip)
            if "VID:PID=10C4:EA60" in port.hwid or "CP210" in port.description or "Silicon Labs" in port.manufacturer:
                esp32_ports.append(port.device)
                print(f"Found ESP32-S3 candidate: {port.device} - {port.description}")
        
        if esp32_ports:
            esp32_ports.sort(reverse=True)
            
            for port in esp32_ports:
                print(f"Attempting connection on {port}")
                self.serial_manager = SerialManager(port, baudrate=115200, tap=self.serial_tap)
                # Wait for ESP32 to complete boot after reset
                print("Waiting for ESP32 to boot...")
                time.sleep(3.0)
                # Flush any boot messages
                if self.serial_manager.serial:
                    self.serial_manager.serial.reset_input_buffer()
                if self.try_connect():
                    print(f"Successfully connected to ESP32-S3 on {port}")
                    return True
            
            print("Failed to connect to ESP32-S3")
            return False
        
        print("No ESP32-S3 device found")
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
                    if msg_type == "ack":
                        self.connected = True
                        self.last_heartbeat = time.time()
                        print("Received connection acknowledgment")
                        
                        # Send initial configuration immediately
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
            # Get actual apps with volumes and icons
            app_volumes, icons = self.get_application_volumes()
            
            # Convert to lean format
            lean_apps = {}
            for app in app_volumes:
                lean_apps[app["name"]] = {
                    "v": app["volume"],
                    "m": app["muted"],
                    "i": app["has_icon"]
                }
            
            print(f"Sending initial config with {len(lean_apps)} apps")
            success = self.serial_manager.send_message(MSG_INITIAL_CONFIG, {
                "apps": lean_apps
            })
            
            if success:
                # Save as last state to prevent immediate re-send
                self.last_app_list = lean_apps.copy()
                
                # Send icons
                if icons:
                    for icon_info in icons:
                        app_name = icon_info["name"]
                        icon_data = icon_info["icon"]
                        if icon_data:
                            print(f"Sending icon for {app_name}")
                            self.serial_manager.send_icon(app_name, icon_data)
                            time.sleep(0.75)  # Safe delay between icons
            
            return success
        except Exception as e:
            print(f"Error sending initial config: {e}")
            return False

    def send_app_update(self, app_volumes, icons_to_send=None):
        """Send app update using lean protocol and send icons"""
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
                    self.last_app_list = lean_apps.copy()
                    
                    # Send icons for apps that have them
                    if icons_to_send:
                        for icon_info in icons_to_send:
                            app_name = icon_info["name"]
                            icon_data = icon_info["icon"]
                            if icon_data:
                                print(f"Sending icon for {app_name}")
                                self.serial_manager.send_icon(app_name, icon_data)
                                time.sleep(0.75)  # Safe delay between icons
                
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
                abs_volume = payload.get("v") # Absolute volume 0-100
                
                print(f"Received volume command for {app_name}: d={direction}, v={abs_volume}")  # Debug print
                
                if app_name:
                    success = False
                    
                    if abs_volume is not None:
                        # Absolute volume setting
                        print(f"Setting {app_name} volume to {abs_volume}")
                        if app_name == "Master":
                            success = self.set_master_volume(abs_volume)
                        else:
                            success = self.set_app_volume(app_name, abs_volume)
                        new_volume = abs_volume
                        
                    elif direction is not None:
                        # Relative volume setting
                        current_volume = None
                        if app_name == "Master":
                            current_volume = self.get_master_volume()
                        else:
                            sessions = AudioUtilities.GetAllSessions()
                            for session in sessions:
                                if session.Process and session.Process.name() == app_name:
                                    volume_interface = session.SimpleAudioVolume
                                    current_volume = int(volume_interface.GetMasterVolume() * 100)
                                    break
                        
                        if current_volume is not None:
                            new_volume = max(0, min(100, current_volume + (2 if direction else -2)))
                            print(f"Adjusting {app_name} volume from {current_volume} to {new_volume}")
                            
                            if app_name == "Master":
                                success = self.set_master_volume(new_volume)
                            else:
                                success = self.set_app_volume(app_name, new_volume)
                    
                    if success:
                        print(f"Successfully adjusted volume for {app_name}")
                        self.serial_manager.send_volume_ack(app_name, new_volume)
                        
                        # Get current app volumes and send update
                        app_volumes, _ = self.get_application_volumes()
                        self.send_app_update(app_volumes)
                    else:
                        print(f"Failed to adjust volume for {app_name}")

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
                
                # Send update with icons if needed
                if self.send_app_update(app_volumes, icons):
                    self.last_update = current_time
                
            time.sleep(0.01)
            
        except Exception as e:
            print(f"Update error: {e}")
            time.sleep(1) # Prevent rapid looping on error
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
    args = parse_args()
    serial_tap = None

    if args.serial_tap_port:
        try:
            serial_tap = SerialTapServer(
                host=args.serial_tap_host,
                port=args.serial_tap_port,
            )
            print(
                f"Serial tap listening on {args.serial_tap_host}:{args.serial_tap_port} "
                "(connect via telnet/netcat to mirror traffic)"
            )
        except OSError as exc:
            print(f"Failed to start serial tap server: {exc}")

    monitor = VolumeMonitor(serial_tap=serial_tap)
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
        if serial_tap:
            serial_tap.close()
        print("Volume Monitor stopped")

if __name__ == "__main__":
    main()

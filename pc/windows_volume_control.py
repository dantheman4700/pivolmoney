import serial
import json
import time
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
import serial.tools.list_ports

def find_pico_com_port():
    """Find the COM port for the Pico device"""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Look for RPI-RP2 in the description
        if "RPI-RP2" in port.description:
            return port.device
    return None

def get_application_volumes():
    """Get list of applications and their volumes"""
    sessions = AudioUtilities.GetAllSessions()
    app_volumes = []
    
    for session in sessions:
        if session.Process and session.Process.name():
            volume = session.SimpleAudioVolume.GetMasterVolume()
            app_volumes.append({
                "name": session.Process.name(),
                "volume": int(volume * 100)
            })
    
    return app_volumes

def set_application_volume(app_name, volume):
    """Set volume for a specific application"""
    sessions = AudioUtilities.GetAllSessions()
    
    for session in sessions:
        if session.Process and session.Process.name() == app_name:
            volume_interface = session.SimpleAudioVolume
            volume_interface.SetMasterVolume(volume / 100, None)
            return True
    
    return False

def main():
    # Find Pico's COM port
    com_port = find_pico_com_port()
    if not com_port:
        print("Could not find Pico device!")
        return
    
    print(f"Found Pico on {com_port}")
    
    try:
        # Open serial connection
        ser = serial.Serial(com_port, 115200, timeout=1)
        print("Serial connection established")
        
        while True:
            # Check for incoming messages
            if ser.in_waiting:
                try:
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        data = json.loads(line)
                        
                        if data["type"] == "request_apps":
                            # Send list of apps and their volumes
                            app_volumes = get_application_volumes()
                            response = {
                                "type": "apps",
                                "data": app_volumes
                            }
                            ser.write((json.dumps(response) + '\n').encode('utf-8'))
                        
                        elif data["type"] == "set_volume":
                            # Set volume for specific app
                            success = set_application_volume(
                                data["app"],
                                data["volume"]
                            )
                            response = {
                                "type": "volume_set",
                                "success": success,
                                "app": data["app"]
                            }
                            ser.write((json.dumps(response) + '\n').encode('utf-8'))
                
                except json.JSONDecodeError:
                    print("Invalid JSON received")
                except Exception as e:
                    print(f"Error processing message: {e}")
            
            time.sleep(0.1)  # Small delay to prevent CPU hogging
            
    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        if 'ser' in locals():
            ser.close()

if __name__ == "__main__":
    main() 
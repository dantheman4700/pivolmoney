import sys
import select
import json

def init_serial():
    """Initialize serial communication"""
    # Configure USB CDC for high speed
    sys.stdin.buffer.read()  # Clear any pending input
    return True

def read_serial_data():
    """Read data from serial if available"""
    if select.select([sys.stdin], [], [], 0)[0]:
        try:
            data = sys.stdin.buffer.readline()
            return json.loads(data.decode().strip())
        except Exception as e:
            print(f"Error reading serial: {e}")
    return None

def send_serial_data(data):
    """Send data over serial"""
    try:
        json_str = json.dumps(data)
        sys.stdout.write(json_str + '\n')
        sys.stdout.flush()
        return True
    except Exception as e:
        print(f"Error sending serial: {e}")
        return False

# Example message formats:
# From PC to Pico:
# {"type": "apps", "data": [{"name": "Chrome", "volume": 75}, {"name": "Spotify", "volume": 100}]}
# 
# From Pico to PC:
# {"type": "request_apps"}  # Request app list
# {"type": "set_volume", "app": "Chrome", "volume": 50}  # Set app volume 
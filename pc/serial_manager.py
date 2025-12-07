import serial
import time
import logging
import json
import binascii

# Message Types
MSG_HEARTBEAT = "hb"     # Heartbeat
MSG_CONNECT = "conn"     # Connection/handshake
MSG_ICON_REQ = "ireq"    # Icon request
MSG_ICON_TRANSFER = "itr" # Icon transfer
MSG_UPDATE = "upd"       # State update
MSG_ERROR = "err"        # Error message
MSG_ACK = "ack"         # Acknowledgment
MSG_INITIAL_CONFIG = "init"  # Initial configuration
MSG_VOLUME_CMD = "vcmd"  # Volume command acknowledgment

class SerialManager:
    def __init__(self, port, baudrate=115200, timeout=1, tap=None):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        self.last_heartbeat = 0
        self.heartbeat_timeout = 5.0
        self.tap = tap

        try:
            self.serial = serial.Serial(port, baudrate, timeout=timeout)
            self.serial.dtr = False  # Don't reset ESP32
            self.serial.rts = False  # Don't reset ESP32
            time.sleep(0.1)  # Small delay for connection to stabilize
            self.logger.info(f"Serial port {port} opened at {baudrate} baud.")
        except Exception as e:
            self.logger.error(f"Failed to open serial port {port}: {str(e)}")
            self.serial = None

    def _tap(self, direction, payload):
        if self.tap:
            try:
                self.tap.broadcast(direction, payload)
            except Exception as exc:
                self.logger.debug(f"Tap broadcast error: {exc}")

    def send_message(self, msg_type, payload=None):
        """Send a message using Simple Text Protocol"""
        if not self.serial or not self.serial.is_open:
            self.logger.error("Cannot send message - serial port not open")
            return False

        try:
            msg_str = ""
            if msg_type == "conn":
                msg_str = "CONN"
            elif msg_type == "upd" or msg_type == "init":
                # Payload: {"apps": {"Chrome": {"v": 50...}, ...}}
                apps = payload.get("apps", {})
                parts = []
                
                # Check if it's a list (old/standard) or dict (lean)
                if isinstance(apps, list):
                    for app in apps:
                        name = app["name"].replace(",", "").replace("|", "").replace(":", "")
                        if len(name) > 15: name = name[:15]
                        vol = int(app["vol"])
                        parts.append(f"{name}:{vol}")
                elif isinstance(apps, dict):
                    for name, data in apps.items():
                        sanitized_name = name.replace(",", "").replace("|", "").replace(":", "")
                        if len(sanitized_name) > 15: sanitized_name = sanitized_name[:15]
                        vol = int(data["v"])
                        parts.append(f"{sanitized_name}:{vol}")
                        
                msg_str = "UPD|" + ",".join(parts)
            elif msg_type == "hb":
                # msg_str = "HB" 
                return True # Optimisation
            
            if msg_str:
                self._tap("TX", msg_str)
                self.serial.write((msg_str + "\n").encode())
                self.serial.flush()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to send message: {str(e)}")
            return False

    def read_message(self):
        """Read a line (ACK or other)"""
        if not self.serial or not self.serial.is_open:
            return None, None

        try:
            if self.serial.in_waiting:
                line = self.serial.readline().decode(errors="ignore").strip()
                if line:
                    self._tap("RX", line)
                    
                    if line == "ACK":
                        return "ack", {}
                        
                    return "unknown", {"raw": line}
            return None, None
        except Exception as e:
            self.logger.error(f"Error reading message: {str(e)}")
            return None, None

    def send_icon(self, app_name, icon_data):
        """
        Send an icon using base64 encoding in a single message.
        icon_data should be bytes in RGB565 format.
        """
        try:
            if not icon_data:
                self.logger.error("Icon data is None or empty")
                return False
                
            self.logger.debug(f"Sending icon for {app_name}, raw size: {len(icon_data)} bytes")
            b64_data = binascii.b2a_base64(icon_data).decode().strip()
            self.logger.debug(f"Base64 encoded size: {len(b64_data)} bytes")
            
            payload = {
                "n": app_name,
                "d": b64_data
            }
            return self.send_message("itr", payload)
        except Exception as e:
            self.logger.error(f"Error sending icon: {str(e)}")
            return False

    def send_heartbeat(self):
        """Send a minimal heartbeat message"""
        return self.send_message("hb")

    def send_volume_ack(self, app_name, volume):
        """Send volume command acknowledgment"""
        return self.send_message(MSG_VOLUME_CMD, {
            "app": app_name,
            "v": volume
        })

    def check_connection(self):
        """Check if connection is alive based on heartbeat"""
        if not self.serial or not self.serial.is_open:
            return False
        return time.time() - self.last_heartbeat < self.heartbeat_timeout

    def close(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.logger.info("Serial port closed.")
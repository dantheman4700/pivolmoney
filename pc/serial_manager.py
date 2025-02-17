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
    def __init__(self, port, baudrate=115200, timeout=1):
        """Initialize serial connection with specified port"""
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)  # Set to DEBUG to see detailed messages
        
        # Add a console handler if none exists
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        self.last_heartbeat = 0
        self.heartbeat_timeout = 5.0  # 5 seconds
        try:
            self.serial = serial.Serial(port, baudrate, timeout=timeout)
            self.logger.info(f"Serial port {port} opened at {baudrate} baud.")
        except Exception as e:
            self.logger.error(f"Failed to open serial port {port}: {str(e)}")
            self.serial = None

    def send_message(self, msg_type, payload=None):
        """Send a message with type and optional payload"""
        if not self.serial or not self.serial.is_open:
            self.logger.error("Cannot send message - serial port not open")
            return False

        try:
            message = {
                "t": msg_type,
                "p": payload if payload is not None else {}
            }
            json_str = json.dumps(message)
            if not json_str.endswith('\n'):
                json_str += '\n'
            self.logger.debug(f"Sending message: {json_str.strip()}")  # Log the message being sent
            self.serial.write(json_str.encode())
            self.serial.flush()  # Ensure the message is sent immediately
            return True
        except Exception as e:
            self.logger.error(f"Failed to send message: {str(e)}")
            return False

    def read_message(self):
        """
        Read a message in the lean protocol format.
        Returns tuple of (type, payload) or (None, None) if no message.
        """
        if not self.serial or not self.serial.is_open:
            return None, None

        try:
            line = self.serial.readline().decode().strip()
            if line:
                self.logger.debug(f"Received: {line}")
                message = json.loads(line)
                msg_type = message.get("t")
                
                # Update heartbeat time if we receive any valid message
                if msg_type:
                    self.last_heartbeat = time.time()
                
                return msg_type, message.get("p", {})
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
            # Add size checks and logging
            if not icon_data:
                self.logger.error("Icon data is None or empty")
                return False
                
            self.logger.debug(f"Sending icon for {app_name}, raw size: {len(icon_data)} bytes")
            b64_data = binascii.b2a_base64(icon_data).decode().strip()  # Strip any trailing newlines
            self.logger.debug(f"Base64 encoded size: {len(b64_data)} bytes")
            
            payload = {
                "n": app_name,  # Short key for name
                "d": b64_data   # Short key for data
            }
            return self.send_message("itr", payload)  # Icon transfer message
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
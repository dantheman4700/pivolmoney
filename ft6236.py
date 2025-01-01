from machine import Pin, I2C
import time

# FT6236 I2C address
TOUCH_I2C_ADDR = const(0x38)

# Register addresses
REG_MODE_CONTROL = const(0x00)
REG_GEST_ID = const(0x01)
REG_TD_STATUS = const(0x02)
REG_P1_XH = const(0x03)
REG_P1_XL = const(0x04)
REG_P1_YH = const(0x05)
REG_P1_YL = const(0x06)
REG_P1_WEIGHT = const(0x07)
REG_P1_MISC = const(0x08)

class FT6236:
    def __init__(self, i2c, sda_pin, scl_pin):
        """Initialize touch controller with I2C pins"""
        self.i2c = i2c
        self.address = TOUCH_I2C_ADDR
        
        # Try to read chip ID to verify communication
        try:
            self.i2c.writeto(self.address, bytes([0x00]))
            data = self.i2c.readfrom(self.address, 1)
            print(f"Touch ID: {hex(data[0])}")
        except Exception as e:
            print(f"Error initializing touch controller: {e}")
            raise
    
    def _read_reg(self, reg, length=1):
        """Read register(s)"""
        self.i2c.writeto(self.address, bytes([reg]))
        return self.i2c.readfrom(self.address, length)
    
    def read_touch(self):
        """Read touch data. Returns tuple (touched, x, y) or None if error"""
        try:
            # Read touch status
            status = self._read_reg(REG_TD_STATUS)[0]
            if not status:  # No touch detected
                return False, 0, 0
            
            # Read X coordinate (12 bits)
            x_h = self._read_reg(REG_P1_XH)[0]
            x_l = self._read_reg(REG_P1_XL)[0]
            x = ((x_h & 0x0F) << 8) | x_l
            
            # Read Y coordinate (12 bits)
            y_h = self._read_reg(REG_P1_YH)[0]
            y_l = self._read_reg(REG_P1_YL)[0]
            y = ((y_h & 0x0F) << 8) | y_l
            
            return True, x, y
            
        except Exception as e:
            print(f"Error reading touch data: {e}")
            return False, 0, 0
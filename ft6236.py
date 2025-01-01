from micropython import const

# FT6236 I2C Address
_FT6236_ADDR = const(0x38)

# Register definitions
_FT6236_REG_MODE = const(0x00)
_FT6236_REG_GEST = const(0x01)
_FT6236_REG_STATUS = const(0x02)
_FT6236_REG_TOUCH1_X = const(0x03)
_FT6236_REG_TOUCH1_Y = const(0x05)
_FT6236_REG_TOUCH2_X = const(0x09)
_FT6236_REG_TOUCH2_Y = const(0x0B)

class FT6236:
    def __init__(self, i2c, addr=_FT6236_ADDR):
        self.i2c = i2c
        self.addr = addr
        self.buf = bytearray(1)
        
        # Try to read the first register to check if device exists
        try:
            self.i2c.readfrom_mem_into(self.addr, _FT6236_REG_MODE, self.buf)
        except:
            raise RuntimeError("FT6236 not found")
            
    @property
    def touched(self):
        """Returns True if there is at least one touch detected"""
        self.i2c.readfrom_mem_into(self.addr, _FT6236_REG_STATUS, self.buf)
        return (self.buf[0] & 0x0F) > 0
        
    @property
    def touches(self):
        """Returns a list of active touch points"""
        points = []
        self.i2c.readfrom_mem_into(self.addr, _FT6236_REG_STATUS, self.buf)
        touches = self.buf[0] & 0x0F
        
        if touches > 0:
            # Read first touch point
            buf = bytearray(4)
            self.i2c.readfrom_mem_into(self.addr, _FT6236_REG_TOUCH1_X, buf)
            x = ((buf[0] & 0x0F) << 8) | buf[1]
            y = ((buf[2] & 0x0F) << 8) | buf[3]
            points.append((x, y))
            
            if touches > 1:
                # Read second touch point
                self.i2c.readfrom_mem_into(self.addr, _FT6236_REG_TOUCH2_X, buf)
                x = ((buf[0] & 0x0F) << 8) | buf[1]
                y = ((buf[2] & 0x0F) << 8) | buf[3]
                points.append((x, y))
                
        return points 
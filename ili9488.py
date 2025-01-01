from micropython import const
import time
from machine import Pin, SPI
from font8x8 import font8x8

# ILI9488 Commands
_SWRESET = const(0x01)
_SLPOUT = const(0x11)
_DISPON = const(0x29)
_CASET = const(0x2A)
_PASET = const(0x2B)
_RAMWR = const(0x2C)
_MADCTL = const(0x36)
_COLMOD = const(0x3A)
_PIXFMT = const(0x3A)

def color565(r, g, b):
    """Convert RGB888 to RGB565 format"""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

class ILI9488:
    def __init__(self, spi, dc, cs, rst, width=480, height=320):
        self.spi = spi
        self.dc = dc
        self.cs = cs
        self.rst = rst
        self.width = width
        self.height = height
        
        self.dc.init(Pin.OUT, value=0)
        self.cs.init(Pin.OUT, value=1)
        self.rst.init(Pin.OUT, value=1)
        
        self.reset()
        self.init()
        
    def reset(self):
        print("Resetting display...")
        self.rst.value(0)
        time.sleep_ms(50)
        self.rst.value(1)
        time.sleep_ms(150)
        print("Reset complete")
        
    def init(self):
        print("Starting minimal display initialization...")
        
        # Hardware reset
        self.rst.value(0)
        time.sleep_ms(100)
        self.rst.value(1)
        time.sleep_ms(100)
        print("Reset complete")
        
        # Basic initialization
        self._write_cmd(0x01)    # Software reset
        time.sleep_ms(100)
        
        self._write_cmd(0x11)    # Sleep out
        time.sleep_ms(100)
        
        # Power Control A
        self._write_cmd(0xCB)
        self._write_data(bytearray([0x39, 0x2C, 0x00, 0x34, 0x02]))
        
        # Power Control B
        self._write_cmd(0xCF)
        self._write_data(bytearray([0x00, 0xC1, 0x30]))
        
        # Driver timing control A
        self._write_cmd(0xE8)
        self._write_data(bytearray([0x85, 0x00, 0x78]))
        
        # Driver timing control B
        self._write_cmd(0xEA)
        self._write_data(bytearray([0x00, 0x00]))
        
        # Power on sequence control
        self._write_cmd(0xED)
        self._write_data(bytearray([0x64, 0x03, 0x12, 0x81]))
        
        # Pump ratio control
        self._write_cmd(0xF7)
        self._write_data(bytearray([0x20]))
        
        # Power Control,VRH[5:0]
        self._write_cmd(0xC0)
        self._write_data(bytearray([0x23]))
        
        # Power Control,SAP[2:0];BT[3:0]
        self._write_cmd(0xC1)
        self._write_data(bytearray([0x10]))
        
        # VCM Control
        self._write_cmd(0xC5)
        self._write_data(bytearray([0x3E, 0x28]))
        
        # Memory Access Control
        self._write_cmd(0x36)
        self._write_data(bytearray([0x48]))
        
        # Pixel Format
        self._write_cmd(0x3A)
        self._write_data(bytearray([0x55]))
        
        # Frame Rate Control
        self._write_cmd(0xB1)
        self._write_data(bytearray([0x00, 0x18]))
        
        self._write_cmd(0xB6)    # Display Function Control
        self._write_data(bytearray([0x08, 0x82, 0x27]))
        
        self._write_cmd(0xF2)    # 3Gamma Function Disable
        self._write_data(bytearray([0x00]))
        
        self._write_cmd(0x26)    # Gamma curve selected
        self._write_data(bytearray([0x01]))
        
        # Set Gamma
        self._write_cmd(0xE0)
        self._write_data(bytearray([0x0F, 0x31, 0x2B, 0x0C, 0x0E, 0x08, 0x4E, 0xF1,
                                  0x37, 0x07, 0x10, 0x03, 0x0E, 0x09, 0x00]))
        
        # Set Gamma
        self._write_cmd(0xE1)
        self._write_data(bytearray([0x00, 0x0E, 0x14, 0x03, 0x11, 0x07, 0x31, 0xC1,
                                  0x48, 0x08, 0x0F, 0x0C, 0x31, 0x36, 0x0F]))
        
        self._write_cmd(0x29)    # Display on
        time.sleep_ms(100)
        
        print("Basic initialization complete")
        
    def fill(self, color):
        """Fill the entire screen with a color"""
        print(f"Attempting to fill with color: 0x{color:04X}")
        
        # Set column address
        self._write_cmd(0x2A)
        self._write_data(bytearray([0x00, 0x00, 0x01, 0xDF]))  # 0 to 479
        
        # Set row address
        self._write_cmd(0x2B)
        self._write_data(bytearray([0x00, 0x00, 0x01, 0x3F]))  # 0 to 319
        
        # Write to RAM
        self._write_cmd(0x2C)
        
        # Prepare color bytes
        color_hi = color >> 8
        color_lo = color & 0xFF
        
        # Create a buffer for one row of pixels
        buf_size = self.width * 2  # One full row
        row_buffer = bytearray(buf_size)
        for i in range(0, buf_size, 2):
            row_buffer[i] = color_hi
            row_buffer[i + 1] = color_lo
        
        # Write row by row
        self.cs.value(0)
        self.dc.value(1)
        
        for row in range(self.height):
            self.spi.write(row_buffer)
            if row % 32 == 0:  # Print progress every 32 rows
                print(f"Writing row {row}")
        
        self.cs.value(1)
        print("Fill complete")
        
    def _set_window(self, x0, y0, x1, y1):
        """Set the active window for drawing"""
        # Ensure coordinates are within bounds
        x0 = max(0, min(self.width - 1, x0))
        x1 = max(0, min(self.width - 1, x1))
        y0 = max(0, min(self.height - 1, y0))
        y1 = max(0, min(self.height - 1, y1))
        
        # Column address set
        self._write_cmd(_CASET)
        self._write_data(bytearray([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF]))
        
        # Row address set
        self._write_cmd(_PASET)
        self._write_data(bytearray([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF]))
        
        # Memory write
        self._write_cmd(_RAMWR)
        
    def pixel(self, x, y, color):
        """Draw a pixel at the specified position"""
        if 0 <= x < self.width and 0 <= y < self.height:
            self._set_window(x, y, x, y)
            color_bytes = bytearray([color >> 8, color & 0xFF])
            self._write_data(color_bytes)
            
    def text(self, text, x, y, color):
        """Draw text at the specified position"""
        for char in text:
            if 0 <= x < self.width - 8 and 0 <= y < self.height - 8:
                for row in range(8):
                    for col in range(8):
                        if font8x8[ord(char)][row] & (1 << (7-col)):
                            self.pixel(x + col, y + row, color)
            x += 8 
        
    def _write_cmd(self, cmd):
        """Write command with debug"""
        print(f"Writing command: 0x{cmd:02X}")
        self.cs.value(0)
        self.dc.value(0)
        self.spi.write(bytearray([cmd]))
        self.cs.value(1)
        time.sleep_ms(1)  # Small delay between commands
        
    def _write_data(self, data):
        """Write data with debug"""
        print(f"Writing data: {[hex(x) for x in data]}")
        self.cs.value(0)
        self.dc.value(1)
        self.spi.write(data)
        self.cs.value(1)
        time.sleep_ms(1)  # Small delay between data
        
    def fill_rect(self, x, y, w, h, color):
        """Fill a rectangle area with a color"""
        # Ensure coordinates are within bounds
        x = max(0, min(self.width - 1, x))
        y = max(0, min(self.height - 1, y))
        w = min(w, self.width - x)
        h = min(h, self.height - y)
        
        # Set window
        self._write_cmd(_CASET)
        self._write_data(bytearray([x >> 8, x & 0xFF, (x + w - 1) >> 8, (x + w - 1) & 0xFF]))
        
        self._write_cmd(_PASET)
        self._write_data(bytearray([y >> 8, y & 0xFF, (y + h - 1) >> 8, (y + h - 1) & 0xFF]))
        
        # Write to RAM
        self._write_cmd(_RAMWR)
        
        # Prepare color bytes
        color_hi = color >> 8
        color_lo = color & 0xFF
        
        # Create small buffer
        buf_size = min(32, w * 2)  # 2 bytes per pixel
        color_buf = bytearray(buf_size)
        for i in range(0, buf_size, 2):
            color_buf[i] = color_hi
            color_buf[i + 1] = color_lo
            
        # Write data
        self.cs.value(0)
        self.dc.value(1)
        
        # Fill rectangle
        remaining_pixels = w * h
        while remaining_pixels > 0:
            chunk_pixels = min(buf_size // 2, remaining_pixels)
            chunk_bytes = chunk_pixels * 2
            self.spi.write(color_buf[:chunk_bytes])
            remaining_pixels -= chunk_pixels
            
        self.cs.value(1) 
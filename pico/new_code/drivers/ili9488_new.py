from micropython import const
import time
from machine import Pin, SPI
from drivers.font8x8 import font8x8
from core.logger import get_logger
from core.config import (
    DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_ROTATION,
    SPI_BAUDRATE, COLOR_BLACK
)

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
    def __init__(self, spi, dc, cs, rst, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT):
        self.logger = get_logger()
        self.spi = spi
        self.dc = dc
        self.cs = cs
        self.rst = rst
        self.width = width
        self.height = height
        
        # Initialize pins (no need to reinitialize as they're already set up)
        # Just store the references
        self.dc = dc
        self.cs = cs
        self.rst = rst
        
        # No need to reinitialize SPI as it's already set up
        
        self.reset()
        self.init()
        
    def reset(self):
        self.logger.info("Resetting display...")
        self.rst.value(0)
        time.sleep_ms(50)
        self.rst.value(1)
        time.sleep_ms(150)
        self.logger.info("Reset complete")
        
    def init(self):
        self.logger.info("Starting display initialization...")
        
        # Hardware reset
        self.rst.value(0)
        time.sleep_ms(100)
        self.rst.value(1)
        time.sleep_ms(100)
        
        # Basic initialization
        self._write_cmd(_SWRESET)    # Software reset
        time.sleep_ms(100)
        
        self._write_cmd(_SLPOUT)     # Sleep out
        time.sleep_ms(100)
        
        # Gamma settings
        self._write_cmd(0xE0)    # Positive Gamma Control
        self._write_data(bytearray([0x00, 0x03, 0x09, 0x08, 0x16, 0x0A, 0x3F, 0x78,
                                  0x4C, 0x09, 0x0A, 0x08, 0x16, 0x1A, 0x0F]))

        self._write_cmd(0xE1)    # Negative Gamma Control
        self._write_data(bytearray([0x00, 0x16, 0x19, 0x03, 0x0F, 0x05, 0x32, 0x45,
                                  0x46, 0x04, 0x0E, 0x0D, 0x35, 0x37, 0x0F]))

        self._write_cmd(0xC0)    # Power Control 1
        self._write_data(bytearray([0x17, 0x15]))

        self._write_cmd(0xC1)    # Power Control 2
        self._write_data(bytearray([0x41]))

        self._write_cmd(0xC5)    # VCOM Control
        self._write_data(bytearray([0x00, 0x12, 0x80]))

        # Memory Access Control
        self._write_cmd(_MADCTL)
        self._write_data(bytearray([0xE8]))  # MY=1, MX=1, MV=1, BGR=1

        # Interface Pixel Format
        self._write_cmd(_PIXFMT)
        self._write_data(bytearray([0x66]))  # 18-bit color format

        # Frame Rate Control
        self._write_cmd(0xB1)
        self._write_data(bytearray([0x00, 0x18]))

        # Display Function Control
        self._write_cmd(0xB6)
        self._write_data(bytearray([0x02, 0x02]))

        # Interface Control
        self._write_cmd(0xF6)
        self._write_data(bytearray([0x01, 0x30, 0x00]))

        # Enable 3G
        self._write_cmd(0xF2)
        self._write_data(bytearray([0x00]))

        # Gamma Set
        self._write_cmd(0x26)
        self._write_data(bytearray([0x01]))

        # Display ON
        self._write_cmd(_DISPON)
        time.sleep_ms(100)
        
        self.logger.info("Display initialization complete")
        
    def fill(self, color):
        """Fill entire display with specified color"""
        self.logger.debug(f"Attempting to fill with color: 0x{color:04X}")
        
        # Convert 16-bit RGB565 to 18-bit RGB666
        r = ((color >> 11) & 0x1F) << 1  # 5 bits to 6 bits
        g = ((color >> 5) & 0x3F)        # 6 bits to 6 bits
        b = (color & 0x1F) << 1          # 5 bits to 6 bits
        
        # Fill the entire screen using fill_rect
        self.fill_rect(0, 0, self.width, self.height, [r, g, b])
        
    def fill_rect(self, x, y, w, h, color):
        """Fill a rectangle area with a color"""
        # Ensure coordinates are within bounds
        x = max(0, min(self.width - 1, x))
        y = max(0, min(self.height - 1, y))
        w = min(w, self.width - x)
        h = min(h, self.height - y)
        
        # Set column address
        self._write_cmd(0x2A)
        self._write_data(bytearray([x >> 8, x & 0xFF, (x + w - 1) >> 8, (x + w - 1) & 0xFF]))
        
        # Set row address
        self._write_cmd(0x2B)
        self._write_data(bytearray([y >> 8, y & 0xFF, (y + h - 1) >> 8, (y + h - 1) & 0xFF]))
        
        # Write to RAM
        self._write_cmd(0x2C)
        
        # If color is a list, it's RGB values for 18-bit color
        if isinstance(color, list):
            r, g, b = color
            color_bytes = bytearray([r, g, b])
        else:
            # Convert 16-bit color to 18-bit
            r = ((color >> 11) & 0x1F) << 1
            g = ((color >> 5) & 0x3F)
            b = (color & 0x1F) << 1
            color_bytes = bytearray([r, g, b])
        
        # Create a larger buffer (about full screen width)
        pixels_per_write = min(w * h, self.width * 2)  # Use larger chunks
        buffer = bytearray(pixels_per_write * 3)  # 3 bytes per pixel
        
        # Fill buffer with color pattern - optimize by copying in chunks
        chunk = bytearray([color_bytes[0], color_bytes[1], color_bytes[2]] * 16)  # Create a small chunk
        chunk_size = len(chunk)
        
        # Fill the buffer by copying the chunk repeatedly
        for i in range(0, len(buffer), chunk_size):
            remaining = len(buffer) - i
            if remaining >= chunk_size:
                buffer[i:i + chunk_size] = chunk
            else:
                buffer[i:i + remaining] = chunk[:remaining]
        
        # Fill rectangle
        self.cs.value(0)
        self.dc.value(1)
        
        # Write in larger chunks
        total_pixels = w * h
        remaining_pixels = total_pixels
        
        while remaining_pixels > 0:
            write_pixels = min(pixels_per_write, remaining_pixels)
            self.spi.write(buffer[:write_pixels * 3])
            remaining_pixels -= write_pixels
        
        self.cs.value(1)
        
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
        """Write command"""
        self.cs.value(0)
        self.dc.value(0)
        self.spi.write(bytearray([cmd]))
        self.cs.value(1)
        
    def _write_data(self, data):
        """Write data"""
        self.cs.value(0)
        self.dc.value(1)
        self.spi.write(data)
        self.cs.value(1)
        
    def draw_char(self, char, x, y, color, bg_color=None, scale=1):
        """Draw a single character at position x,y with given color and optional background"""
        try:
            char_code = ord(char)
            if char_code not in font8x8:  # Check if character is in our font
                self.logger.warning(f"Character not found in font: {char}")
                return
                
            # Get the character pattern from font8x8
            char_pattern = font8x8[char_code]
            
            # Calculate dimensions
            width = 8 * scale
            height = 8 * scale
            
            # Convert colors to 18-bit format
            if isinstance(color, list):
                color_bytes = bytearray(color)
            else:
                # Convert 16-bit color to 18-bit
                r = ((color >> 11) & 0x1F) << 1
                g = ((color >> 5) & 0x3F)
                b = (color & 0x1F) << 1
                color_bytes = bytearray([r, g, b])
                
            if bg_color is not None:
                if isinstance(bg_color, list):
                    bg_bytes = bytearray(bg_color)
                else:
                    r = ((bg_color >> 11) & 0x1F) << 1
                    g = ((bg_color >> 5) & 0x3F)
                    b = (bg_color & 0x1F) << 1
                    bg_bytes = bytearray([r, g, b])
            else:
                bg_bytes = bytearray([0, 0, 0])  # Black background
            
            # Set drawing window
            self._write_cmd(_CASET)  # Column address set
            self._write_data(bytearray([x >> 8, x & 0xFF, (x + width - 1) >> 8, (x + width - 1) & 0xFF]))
            
            self._write_cmd(_PASET)  # Row address set
            self._write_data(bytearray([y >> 8, y & 0xFF, (y + height - 1) >> 8, (y + height - 1) & 0xFF]))
            
            self._write_cmd(_RAMWR)  # Memory write
            
            # Create buffer for one row of scaled pixels
            buffer = bytearray(width * 3)  # 3 bytes per pixel
            
            # Draw character pixel by pixel with scaling
            self.cs.value(0)
            self.dc.value(1)
            
            for row in range(8):
                pattern = char_pattern[row]
                
                # Fill buffer for one row
                for col in range(8):
                    pixel_on = pattern & (1 << (7-col))
                    pixel_bytes = color_bytes if pixel_on else bg_bytes
                    
                    # Scale horizontally by duplicating pixels
                    for sx in range(scale):
                        idx = (col * scale + sx) * 3
                        buffer[idx:idx+3] = pixel_bytes
                
                # Repeat the row scale times
                for sy in range(scale):
                    self.spi.write(buffer)
            
            self.cs.value(1)
            
        except Exception as e:
            self.logger.error(f"Error drawing character '{char}': {str(e)}")
        
    def draw_text(self, x, y, text, color, bg_color=None, scale=1):
        """Draw text string at position x,y with given color and optional background"""
        cursor_x = x
        cursor_y = y
        char_spacing = scale  # Space between characters
        
        for char in text:
            if char == '\n':  # Handle newline
                cursor_x = x
                cursor_y += 8 * scale + char_spacing
                continue
                
            if cursor_x + 8 * scale > self.width:  # Handle text wrapping
                cursor_x = x
                cursor_y += 8 * scale + char_spacing
            
            self.draw_char(char, cursor_x, cursor_y, color, bg_color, scale)
            cursor_x += 8 * scale + char_spacing
            
    def draw_rectangle(self, x, y, width, height, color, filled=False):
        """Draw a rectangle at (x,y) with given width, height and color"""
        if filled:
            for i in range(height):
                self.draw_hline(x, y + i, width, color)
        else:
            self.draw_hline(x, y, width, color)  # Top
            self.draw_hline(x, y + height - 1, width, color)  # Bottom
            self.draw_vline(x, y, height, color)  # Left
            self.draw_vline(x + width - 1, y, height, color)  # Right

    def draw_button(self, x, y, width, height, text, text_color, button_color, border_color=None):
        """Draw a button with text centered in it"""
        # Draw button background
        self.draw_rectangle(x, y, width, height, button_color, filled=True)
        
        # Draw border if specified
        if border_color is not None:
            self.draw_rectangle(x, y, width, height, border_color)
        
        # Center text in button
        text_width = len(text) * 8  # Assuming 8x8 font
        text_x = x + (width - text_width) // 2
        text_y = y + (height - 8) // 2  # Assuming 8x8 font
        self.draw_text(text_x, text_y, text, text_color, button_color)

    def draw_progress_bar(self, x, y, width, height, percentage, bar_color, background_color=None, border_color=None):
        """Draw a progress bar with given percentage (0-100)"""
        # Draw background if specified
        if background_color is not None:
            self.draw_rectangle(x, y, width, height, background_color, filled=True)
        
        # Draw border if specified
        if border_color is not None:
            self.draw_rectangle(x, y, width, height, border_color)
        
        # Calculate bar width based on percentage
        bar_width = int((width - 2) * percentage / 100)
        if bar_width > 0:
            self.draw_rectangle(x + 1, y + 1, bar_width, height - 2, bar_color, filled=True)

    def draw_list_item(self, x, y, width, height, text, text_color, background_color, selected=False):
        """Draw a list item with optional selection highlight"""
        # Draw background
        self.draw_rectangle(x, y, width, height, background_color, filled=True)
        
        # Draw selection indicator if selected
        if selected:
            self.draw_rectangle(x, y, width, height, text_color)
            # Draw small arrow or marker
            self.draw_rectangle(x + 2, y + height//2 - 2, 4, 4, text_color, filled=True)
        
        # Draw text with padding
        if hasattr(self, 'draw_text'):
            self.draw_text(x + 8, y + (height - 8)//2, text, text_color)

    def clear_rect(self, x, y, width, height):
        """Clear a rectangular area (fill with black)"""
        self.draw_rectangle(x, y, width, height, 0x0000, filled=True) 

    def draw_hline(self, x, y, width, color):
        """Draw a horizontal line"""
        self.fill_rect(x, y, width, 1, color)
        
    def draw_vline(self, x, y, height, color):
        """Draw a vertical line"""
        self.fill_rect(x, y, 1, height, color)
        
    def fill_circle(self, x0, y0, radius, color):
        """Draw a filled circle at (x0,y0) with given radius and color"""
        x = radius
        y = 0
        err = 0
        
        # Convert color to RGB666 format if it's RGB565
        if not isinstance(color, list):
            r = ((color >> 11) & 0x1F) << 1
            g = ((color >> 5) & 0x3F)
            b = (color & 0x1F) << 1
            color = [r, g, b]
            
        while x >= y:
            self.fill_rect(x0 - x, y0 + y, 2*x + 1, 1, color)
            self.fill_rect(x0 - x, y0 - y, 2*x + 1, 1, color)
            self.fill_rect(x0 - y, y0 + x, 2*y + 1, 1, color)
            self.fill_rect(x0 - y, y0 - x, 2*y + 1, 1, color)
            
            y += 1
            err += 1 + 2*y
            if 2*(err-x) + 1 > 0:
                x -= 1
                err += 1 - 2*x
        
    def draw_icon(self, x, y, icon_data, width=48, height=38):
        """Draw an icon from raw RGB565 data"""
        if not icon_data:
            return
        
        try:
            # Set drawing window
            self._write_cmd(_CASET)
            self._write_data(bytearray([x >> 8, x & 0xFF, (x + width - 1) >> 8, (x + width - 1) & 0xFF]))
            
            self._write_cmd(_PASET)
            self._write_data(bytearray([y >> 8, y & 0xFF, (y + height - 1) >> 8, (y + height - 1) & 0xFF]))
            
            self._write_cmd(_RAMWR)
            
            # Write data in rows to minimize memory usage
            self.cs.value(0)
            self.dc.value(1)
            
            # Process one row at a time
            row_size = width * 2  # 2 bytes per pixel in RGB565
            for i in range(0, len(icon_data), row_size):
                row = icon_data[i:i + row_size]
                self.spi.write(row)
            
            self.cs.value(1)
            
        except Exception as e:
            self.logger.error(f"Error drawing icon: {str(e)}")

    def draw_line(self, x0, y0, x1, y1, color):
        """Draw a line from (x0,y0) to (x1,y1)"""
        try:
            # Convert color to RGB666 format if it's RGB565
            if not isinstance(color, list):
                r = ((color >> 11) & 0x1F) << 1
                g = ((color >> 5) & 0x3F)
                b = (color & 0x1F) << 1
                color = [r, g, b]
            
            # Use Bresenham's line algorithm
            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            steep = dy > dx
            
            # If line is steep, transpose coordinates
            if steep:
                x0, y0 = y0, x0
                x1, y1 = y1, x1
            
            # Ensure line is drawn from left to right
            if x0 > x1:
                x0, x1 = x1, x0
                y0, y1 = y1, y0
            
            dx = x1 - x0
            dy = abs(y1 - y0)
            err = dx // 2
            
            if y0 < y1:
                ystep = 1
            else:
                ystep = -1
            
            # Draw the line pixel by pixel
            y = y0
            for x in range(x0, x1 + 1):
                if steep:
                    self.fill_rect(y, x, 1, 1, color)
                else:
                    self.fill_rect(x, y, 1, 1, color)
                
                err -= dy
                if err < 0:
                    y += ystep
                    err += dx
                    
        except Exception as e:
            self.logger.error(f"Error drawing line: {str(e)}")

 
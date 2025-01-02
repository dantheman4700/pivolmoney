"""
Icon storage and rendering for common applications.
Icons are stored as 32x32 pixel arrays in 18-bit RGB format.
"""

# Example icon data structure (we'll need to create actual icon data)
ICON_SIZE = 32  # 32x32 pixels

# Placeholder icon data (checkerboard pattern for testing)
def create_test_icon(color1, color2):
    icon_data = []
    for y in range(ICON_SIZE):
        row = []
        for x in range(ICON_SIZE):
            if (x + y) % 2 == 0:
                row.extend(color1)  # RGB values
            else:
                row.extend(color2)  # RGB values
        icon_data.extend(row)
    return bytearray(icon_data)

# Create some test icons
ICONS = {
    'chrome': create_test_icon([0x00, 0x00, 0xFF], [0xFF, 0xFF, 0xFF]),  # Blue and white
    'spotify': create_test_icon([0x00, 0xFF, 0x00], [0x00, 0x00, 0x00]),  # Green and black
    'discord': create_test_icon([0x88, 0x88, 0xFF], [0x44, 0x44, 0xFF]),  # Discord colors
    'default': create_test_icon([0x80, 0x80, 0x80], [0x40, 0x40, 0x40]),  # Gray pattern
}

def draw_icon(display, x, y, app_name):
    """Draw an application icon at the specified position"""
    icon_data = ICONS.get(app_name.lower(), ICONS['default'])
    
    # Set up drawing window
    display._write_cmd(0x2A)  # Column address set
    display._write_data(bytearray([x >> 8, x & 0xFF, (x + ICON_SIZE - 1) >> 8, (x + ICON_SIZE - 1) & 0xFF]))
    
    display._write_cmd(0x2B)  # Row address set
    display._write_data(bytearray([y >> 8, y & 0xFF, (y + ICON_SIZE - 1) >> 8, (y + ICON_SIZE - 1) & 0xFF]))
    
    display._write_cmd(0x2C)  # Memory write
    
    # Write icon data
    display.cs.value(0)
    display.dc.value(1)
    
    # Write the entire icon at once
    display.spi.write(icon_data)
    
    display.cs.value(1) 
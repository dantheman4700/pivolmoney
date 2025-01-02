"""
Icon storage and rendering for common applications.
Icons are stored as 32x32 pixel arrays in 18-bit RGB format.
"""

# Icon size definitions
ICON_SIZE = 32  # 32x32 pixels is a good size for our display

# Convert RGB888 to RGB565
def rgb888_to_rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

# Example icon data structure (to be filled with actual icon data)
ICONS = {
    "master": {
        "size": ICON_SIZE,
        "data": []  # Will be filled with RGB565 values
    },
    "spotify": {
        "size": ICON_SIZE,
        "data": []
    },
    "chrome": {
        "size": ICON_SIZE,
        "data": []
    },
    # Add more icons as needed
}

def get_icon(name):
    """Get icon data by name"""
    return ICONS.get(name, None)

# Helper function to draw icon
def draw_icon(display, x, y, icon_name, scale=1):
    """Draw icon at specified position with optional scaling"""
    icon = get_icon(icon_name)
    if not icon:
        return False
    
    size = icon["size"]
    data = icon["data"]
    
    # TODO: Add actual drawing code once we have icon data
    return True 
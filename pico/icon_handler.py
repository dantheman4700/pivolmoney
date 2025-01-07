import binascii
import struct
from micropython import const

# Display constants
ICON_SIZE = const(60)  # Match UI grid size
BLACK = const(0x0000)
WHITE = const(0xFFFF)
GRAY = const(0x7BEF)
DARK_GRAY = const(0x39E7)

def log_to_file(msg):
    """Write log message to file"""
    try:
        with open('pico_serial.log', 'a') as f:
            f.write(str(msg) + '\n')
    except:
        pass

class IconHandler:
    def __init__(self, display):
        self.display = display
        self.icon_cache = {}  # Store processed icons
        log_to_file("IconHandler initialized")
        
    def process_icon_data(self, app_name, base64_data):
        """Process base64 encoded RGB565 data and store in cache"""
        try:
            log_to_file(f"Processing icon for {app_name}")
            
            # Decode base64 directly to RGB565 data
            icon_data = binascii.a2b_base64(base64_data)
            
            # Verify data length (60x60 pixels * 2 bytes per pixel)
            expected_size = ICON_SIZE * ICON_SIZE * 2
            if len(icon_data) != expected_size:
                log_to_file(f"Invalid icon data size: {len(icon_data)} (expected {expected_size})")
                return False
            
            # Store raw RGB565 data
            self.icon_cache[app_name] = icon_data
            log_to_file(f"Successfully processed and cached icon for {app_name}")
            return True
            
        except Exception as e:
            log_to_file(f"Error processing icon for {app_name}: {str(e)}")
            return False
            
    def draw_icon(self, x, y, app_name, selected=False):
        """Draw cached icon at specified position with optional selection highlight"""
        try:
            # Draw background first
            bg_color = GRAY if selected else DARK_GRAY
            self.display.fill_rect(x, y, ICON_SIZE, ICON_SIZE, bg_color)
            
            if app_name not in self.icon_cache:
                log_to_file(f"No cached icon found for {app_name}")
                return False
            
            # Get RGB565 data
            icon_data = self.icon_cache[app_name]
            
            # Set display window and write data directly
            self.display._set_window(x, y, x + ICON_SIZE - 1, y + ICON_SIZE - 1)
            self.display._write_data(icon_data)
            
            return True
            
        except Exception as e:
            log_to_file(f"Error drawing icon for {app_name}: {str(e)}")
            return False
    
    def clear_cache(self):
        """Clear the icon cache"""
        count = len(self.icon_cache)
        self.icon_cache.clear()
        log_to_file(f"Cleared icon cache ({count} icons removed)")
        
    def remove_icon(self, app_name):
        """Remove specific icon from cache"""
        if app_name in self.icon_cache:
            del self.icon_cache[app_name]
            log_to_file(f"Removed icon for {app_name} from cache")
            
    def get_cached_icons(self):
        """Get list of apps with cached icons"""
        icons = list(self.icon_cache.keys())
        log_to_file(f"Currently cached icons: {icons}")
        return icons 
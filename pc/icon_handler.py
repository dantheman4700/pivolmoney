import win32gui
import win32ui
import win32con
import win32api
import win32process
from PIL import Image
import io
import struct

def rgb_to_rgb565(r, g, b):
    """Convert RGB888 to RGB565"""
    r = (r >> 3) & 0x1F
    g = (g >> 2) & 0x3F
    b = (b >> 3) & 0x1F
    return (r << 11) | (g << 5) | b

class IconHandler:
    def __init__(self):
        self.icon_cache = {}  # Cache for storing icons
        self.icon_size = (48, 48)  # Changed to 48x48 square icons
        
    def clear_cache(self):
        """Clear the icon cache"""
        self.icon_cache = {}
        
    def get_icon_for_app(self, process_name, pid):
        """Get icon for an app, using cache if available"""
        cache_key = f"{process_name}_{pid}"
        
        # Check cache first
        if cache_key in self.icon_cache:
            return self.icon_cache[cache_key]
            
        # Try to find window handle for the process
        def callback(hwnd, hwnds):
            if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                if found_pid == pid:
                    hwnds.append(hwnd)
            return True
            
        hwnds = []
        try:
            win32gui.EnumWindows(callback, hwnds)
        except:
            pass
            
        # Try to get icon from any window found
        icon_data = None
        for hwnd in hwnds:
            icon_data = self.get_window_icon(hwnd)
            if icon_data:
                break
                
        # If no icon found, use default
        if not icon_data:
            icon_data = self.get_default_icon()
            
        # Cache the icon
        if icon_data:
            self.icon_cache[cache_key] = icon_data
            
        return icon_data
        
    def get_window_icon(self, hwnd):
        """Get window icon in RGB565 format"""
        try:
            # Try to get the icon handle
            icon_handle = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_BIG, 0)
            if not icon_handle:
                icon_handle = win32gui.GetClassLong(hwnd, win32con.GCL_HICON)
            
            if not icon_handle:
                print(f"No icon handle found for window {hwnd}")
                return None
                
            # Extract icon
            icon = win32gui.DestroyIcon(win32api.CopyIcon(icon_handle))
            if not icon:
                print(f"Failed to copy icon for window {hwnd}")
                return None
                
            # Convert to bitmap
            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, self.icon_size[0], self.icon_size[1])
            hdc = hdc.CreateCompatibleDC()
            hdc.SelectObject(hbmp)
            hdc.DrawIcon((0, 0), icon)
            
            # Convert to PIL Image
            bmpstr = hbmp.GetBitmapBits(True)
            img = Image.frombuffer('RGBA', self.icon_size, bmpstr, 'raw', 'BGRA', 0, 1)
            
            # Convert to RGB565
            rgb565_data = bytearray(self.icon_size[0] * self.icon_size[1] * 2)  # 2 bytes per pixel
            pixels = img.convert('RGB').load()
            for y in range(self.icon_size[1]):
                for x in range(self.icon_size[0]):
                    r, g, b = pixels[x, y]
                    rgb565 = rgb_to_rgb565(r, g, b)
                    idx = (y * self.icon_size[0] + x) * 2
                    rgb565_data[idx] = (rgb565 >> 8) & 0xFF
                    rgb565_data[idx + 1] = rgb565 & 0xFF
            
            print(f"Successfully extracted icon for window {hwnd}")
            return rgb565_data
            
        except Exception as e:
            print(f"Error getting icon for window {hwnd}: {str(e)}")
            return None
            
    def get_default_icon(self):
        """Generate a default icon when window icon cannot be retrieved"""
        try:
            # Create a simple default icon (gray square with white border)
            img = Image.new('RGB', self.icon_size, (128, 128, 128))
            pixels = img.load()
            
            # Add white border
            for x in range(self.icon_size[0]):
                pixels[x, 0] = (255, 255, 255)
                pixels[x, self.icon_size[1]-1] = (255, 255, 255)
            for y in range(self.icon_size[1]):
                pixels[0, y] = (255, 255, 255)
                pixels[self.icon_size[0]-1, y] = (255, 255, 255)
                
            # Convert to RGB565
            rgb565_data = bytearray(self.icon_size[0] * self.icon_size[1] * 2)
            for y in range(self.icon_size[1]):
                for x in range(self.icon_size[0]):
                    r, g, b = pixels[x, y]
                    rgb565 = rgb_to_rgb565(r, g, b)
                    idx = (y * self.icon_size[0] + x) * 2
                    rgb565_data[idx] = (rgb565 >> 8) & 0xFF
                    rgb565_data[idx + 1] = rgb565 & 0xFF
                    
            print("Generated default icon successfully")
            return rgb565_data
            
        except Exception as e:
            print(f"Error creating default icon: {str(e)}")
            return None
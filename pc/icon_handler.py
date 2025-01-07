import win32gui
import win32ui
import win32con
import win32api
import win32process
from PIL import Image
import io
import logging
import base64
import psutil
import struct

class IconHandler:
    def __init__(self):
        self.icon_cache = {}  # Cache icons by process name and pid
        self.ICON_SIZE = 60  # Match UI grid size
        
    def get_icon_for_app(self, process_name, pid=None):
        """Get icon for an application by process name and optional pid"""
        cache_key = f"{process_name}_{pid}" if pid else process_name
        
        # Check cache first
        if cache_key in self.icon_cache:
            return self.icon_cache[cache_key]
            
        # Find windows for this process
        windows = self.find_process_windows(process_name)
        icon_data = None
        
        for hwnd, _, is_visible in windows:
            if icon_data := self.get_window_icon(hwnd):
                self.icon_cache[cache_key] = icon_data
                return icon_data
                
        return None
        
    def find_process_windows(self, process_name):
        """Find all windows belonging to a process"""
        windows = []
        target_name = process_name.lower().replace('.exe', '')
        
        def callback(hwnd, _):
            if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    process = psutil.Process(pid)
                    if process.name().lower().replace('.exe', '') == target_name:
                        title = win32gui.GetWindowText(hwnd)
                        if title and not title.startswith("Default IME"):
                            windows.append((hwnd, title, True))
                except:
                    pass
            return True
            
        win32gui.EnumWindows(callback, None)
        return windows
        
    def rgb_to_rgb565(self, r, g, b, a):
        """Convert RGBA to RGB565 format with alpha handling"""
        if a < 128:  # If mostly transparent
            return 0x39E7  # Use dark gray for transparent pixels
            
        # Convert to 5/6/5 format
        r = (r >> 3) & 0x1F
        g = (g >> 2) & 0x3F
        b = (b >> 3) & 0x1F
        
        # Combine into 16-bit value
        return (r << 11) | (g << 5) | b
        
    def get_window_icon(self, hwnd):
        """Get icon for a window handle and convert to RGB565 format"""
        try:
            if not win32gui.IsWindow(hwnd):
                return None
                
            # Try to get icon from window class first
            hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_BIG, 0)
            if not hicon:
                hicon = win32gui.GetClassLong(hwnd, win32con.GCL_HICON)
            if not hicon:
                hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_SMALL, 0)
            if not hicon:
                hicon = win32gui.GetClassLong(hwnd, win32con.GCL_HICONSM)
                
            if hicon:
                try:
                    # Get screen DC
                    hdc = win32gui.GetDC(0)
                    
                    # Create memory DC
                    memdc = win32gui.CreateCompatibleDC(hdc)
                    
                    # Create bitmap (60x60 for Pico display)
                    hbmp = win32gui.CreateCompatibleBitmap(hdc, self.ICON_SIZE, self.ICON_SIZE)
                    
                    # Select bitmap into DC
                    old_bitmap = win32gui.SelectObject(memdc, hbmp)
                    
                    # Fill background with white
                    brush = win32gui.CreateSolidBrush(win32api.RGB(255, 255, 255))
                    win32gui.FillRect(memdc, (0, 0, self.ICON_SIZE, self.ICON_SIZE), brush)
                    
                    # Draw the icon
                    win32gui.DrawIconEx(memdc, 0, 0, hicon, self.ICON_SIZE, self.ICON_SIZE, 0, None, win32con.DI_NORMAL)
                    
                    # Get bitmap bits
                    bmp = win32ui.CreateBitmapFromHandle(hbmp)
                    bmpstr = bmp.GetBitmapBits(True)
                    
                    # Convert to PIL Image
                    img = Image.frombuffer(
                        'RGBA',
                        (self.ICON_SIZE, self.ICON_SIZE),
                        bmpstr,
                        'raw',
                        'BGRA',
                        0,
                        1
                    )
                    
                    # Convert to RGB565 format
                    rgb565_data = bytearray(self.ICON_SIZE * self.ICON_SIZE * 2)  # 2 bytes per pixel
                    pixels = img.load()
                    
                    for y in range(self.ICON_SIZE):
                        for x in range(self.ICON_SIZE):
                            r, g, b, a = pixels[x, y]
                            rgb565 = self.rgb_to_rgb565(r, g, b, a)
                            # Store in big-endian format
                            idx = (y * self.ICON_SIZE + x) * 2
                            rgb565_data[idx] = (rgb565 >> 8) & 0xFF
                            rgb565_data[idx + 1] = rgb565 & 0xFF
                    
                    # Convert to base64
                    base64_str = base64.b64encode(rgb565_data).decode('utf-8')
                    
                    # Clean up
                    win32gui.SelectObject(memdc, old_bitmap)
                    win32gui.DeleteObject(hbmp)
                    win32gui.DeleteObject(brush)
                    win32gui.DeleteDC(memdc)
                    win32gui.ReleaseDC(0, hdc)
                    win32gui.DestroyIcon(hicon)
                    
                    return base64_str
                    
                except Exception as e:
                    logging.error(f"Error converting icon: {e}")
                    try:
                        win32gui.DestroyIcon(hicon)
                    except:
                        pass
                    
        except Exception as e:
            logging.error(f"Could not get icon: {e}")
        return None
        
    def clear_cache(self):
        """Clear the icon cache"""
        self.icon_cache.clear()
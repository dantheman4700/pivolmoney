import win32gui
import win32ui
import win32con
import win32api
import win32process
from PIL import Image
import io
import struct
import psutil

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
        
    def get_process_name_without_exe(self, name):
        """Remove .exe from process name for better matching"""
        return name.lower().replace('.exe', '')

    def find_process_windows(self, process_name):
        """Find all windows belonging to processes with the given name"""
        windows = []
        target_name = self.get_process_name_without_exe(process_name)
        
        def callback(hwnd, _):
            if win32gui.IsWindow(hwnd) and win32gui.GetWindowText(hwnd):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    process = psutil.Process(pid)
                    if self.get_process_name_without_exe(process.name()) == target_name:
                        is_visible = win32gui.IsWindowVisible(hwnd)
                        title = win32gui.GetWindowText(hwnd)
                        if title and not title.startswith("Default IME") and not title.startswith("MSCTFIME"):
                            windows.append((hwnd, title, is_visible))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return True
        
        win32gui.EnumWindows(callback, None)
        return windows

    def get_icon_for_app(self, process_name, pid):
        """Get icon for an app, using cache if available"""
        cache_key = f"{process_name}_{pid}"
        
        # Check cache first
        if cache_key in self.icon_cache:
            return self.icon_cache[cache_key]
            
        # Find all windows for this process
        windows = self.find_process_windows(process_name)
        
        # Get icon if we found any windows
        icon_data = None
        if windows:
            print(f"Found {len(windows)} windows for {process_name}")
            visible_windows = [w for w in windows if w[2]]  # Get visible windows
            windows_to_try = visible_windows if visible_windows else windows
            
            for hwnd, title, is_visible in windows_to_try:
                print(f"Trying to get icon for window: {title} (Visible: {is_visible})")
                icon_data = self.get_window_icon(hwnd)
                if icon_data:
                    print(f"Successfully got icon for {title}")
                    break
        else:
            print(f"No windows found for {process_name}")
        
        # If no icon found, use default
        if not icon_data:
            print(f"Using default icon for {process_name}")
            icon_data = self.get_default_icon()
            
        # Cache the icon
        if icon_data:
            self.icon_cache[cache_key] = icon_data
            
        return icon_data
        
    def get_window_icon(self, hwnd):
        """Get window icon in RGB565 format"""
        try:
            if not win32gui.IsWindow(hwnd):
                print(f"Invalid window handle: {hwnd}")
                return None
            
            window_text = win32gui.GetWindowText(hwnd)
            print(f"Attempting to get icon for window: {window_text} (handle: {hwnd})")
            
            # Try to get icon from window class first
            hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_BIG, 0)
            if not hicon:
                # Try to get the icon from the window class
                hicon = win32gui.GetClassLong(hwnd, win32con.GCL_HICON)
            if not hicon:
                # Try to get the small icon
                hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_SMALL, 0)
            if not hicon:
                hicon = win32gui.GetClassLong(hwnd, win32con.GCL_HICONSM)
            
            if hicon:
                print(f"Got icon handle for {window_text}")
                try:
                    # Get screen DC
                    screen_dc = win32gui.GetDC(0)
                    
                    # Create memory DC
                    memdc = win32gui.CreateCompatibleDC(screen_dc)
                    
                    # Create bitmap
                    hbmp = win32gui.CreateCompatibleBitmap(screen_dc, self.icon_size[0], self.icon_size[1])
                    
                    # Select bitmap into DC
                    old_bitmap = win32gui.SelectObject(memdc, hbmp)
                    
                    # Fill background with black (for transparency)
                    brush = win32gui.CreateSolidBrush(win32api.RGB(0, 0, 0))
                    win32gui.FillRect(memdc, (0, 0, self.icon_size[0], self.icon_size[1]), brush)
                    
                    # Draw the icon
                    win32gui.DrawIconEx(memdc, 0, 0, hicon, self.icon_size[0], self.icon_size[1], 0, None, win32con.DI_NORMAL)
                    
                    # Get bitmap bits using win32ui
                    bmp = win32ui.CreateBitmapFromHandle(hbmp)
                    bmpstr = bmp.GetBitmapBits(True)
                    
                    # Convert to PIL Image
                    img = Image.frombuffer(
                        'RGBA',
                        (self.icon_size[0], self.icon_size[1]),
                        bmpstr,
                        'raw',
                        'BGRA',
                        0,
                        1
                    )
                    
                    # Debug: Save first image to check format
                    img.save("debug_icon_rgba.png")
                    
                    # Convert to RGB and save for debug
                    img_rgb = img.convert('RGB')
                    img_rgb.save("debug_icon_rgb.png")
                    
                    # Convert to RGB565
                    rgb565_data = bytearray(self.icon_size[0] * self.icon_size[1] * 2)  # 2 bytes per pixel
                    pixels = img_rgb.load()
                    
                    # Debug: Print first few pixels
                    print("First 4 pixels (RGB):")
                    for y in range(2):
                        for x in range(2):
                            r, g, b = pixels[x, y]
                            print(f"Pixel ({x},{y}): RGB({r},{g},{b})")
                    
                    for y in range(self.icon_size[1]):
                        for x in range(self.icon_size[0]):
                            r, g, b = pixels[x, y]
                            # Convert to RGB565
                            r5 = (r >> 3) & 0x1F  # 5 bits red
                            g6 = (g >> 2) & 0x3F  # 6 bits green
                            b5 = (b >> 3) & 0x1F  # 5 bits blue
                            rgb565 = (r5 << 11) | (g6 << 5) | b5
                            
                            # Store in big-endian format (high byte first)
                            idx = (y * self.icon_size[0] + x) * 2
                            rgb565_data[idx] = (rgb565 >> 8) & 0xFF  # High byte
                            rgb565_data[idx + 1] = rgb565 & 0xFF     # Low byte
                            
                            # Debug first few pixels
                            if y == 0 and x < 2:
                                print(f"Pixel ({x},{y}): RGB({r},{g},{b}) -> RGB565({r5},{g6},{b5}) = 0x{rgb565:04X}")
                    
                    # Debug: Print first few bytes of RGB565 data
                    print("First 8 bytes of RGB565 data:")
                    print(" ".join(f"{b:02X}" for b in rgb565_data[:8]))
                    
                    print(f"Successfully extracted icon for window {window_text}")
                    
                    # Clean up resources
                    win32gui.DeleteObject(brush)
                    win32gui.DeleteObject(hbmp)
                    win32gui.SelectObject(memdc, old_bitmap)
                    win32gui.DeleteDC(memdc)
                    win32gui.ReleaseDC(0, screen_dc)
                    win32gui.DestroyIcon(hicon)
                    
                    return rgb565_data
                    
                except Exception as e:
                    print(f"Error converting icon to image for {window_text}: {e}")
                    try:
                        win32gui.DestroyIcon(hicon)
                    except:
                        pass
                    
            else:
                print(f"No icon found for window {window_text}")
            
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
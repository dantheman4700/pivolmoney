import win32gui
import win32ui
import win32con
import win32api
from PIL import Image
import io
import logging
import base64

class IconHandler:
    @staticmethod
    def get_window_icon(hwnd, size=(32, 32)):
        """Get icon for a window handle and convert to PNG bytes"""
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
                    
                    # Create bitmap
                    hbmp = win32gui.CreateCompatibleBitmap(hdc, size[0], size[1])
                    
                    # Select bitmap into DC
                    old_bitmap = win32gui.SelectObject(memdc, hbmp)
                    
                    # Fill background with white
                    brush = win32gui.CreateSolidBrush(win32api.RGB(255, 255, 255))
                    win32gui.FillRect(memdc, (0, 0, size[0], size[1]), brush)
                    
                    # Draw the icon
                    win32gui.DrawIconEx(memdc, 0, 0, hicon, size[0], size[1], 0, None, win32con.DI_NORMAL)
                    
                    # Get bitmap bits using win32ui
                    bmp = win32ui.CreateBitmapFromHandle(hbmp)
                    bmpstr = bmp.GetBitmapBits(True)
                    
                    # Convert to PIL Image
                    img = Image.frombuffer(
                        'RGBA',
                        size,
                        bmpstr,
                        'raw',
                        'BGRA',
                        0,
                        1
                    )
                    
                    # Convert to PNG bytes
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    img_byte_arr.seek(0)
                    
                    # Convert to base64 for efficient transmission
                    b64_str = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
                    
                    # Clean up
                    win32gui.SelectObject(memdc, old_bitmap)
                    win32gui.DeleteObject(hbmp)
                    win32gui.DeleteObject(brush)
                    win32gui.DeleteDC(memdc)
                    win32gui.ReleaseDC(0, hdc)
                    win32gui.DestroyIcon(hicon)
                    
                    return b64_str
                    
                except Exception as e:
                    logging.error(f"Error converting icon to image: {e}")
                    try:
                        win32gui.DestroyIcon(hicon)
                    except:
                        pass
                    
        except Exception as e:
            logging.error(f"Could not get icon for window: {e}")
        return None

    @staticmethod
    def find_process_windows(process_name):
        """Find all windows belonging to a process"""
        windows = []
        target_name = process_name.lower().replace('.exe', '')
        
        def callback(hwnd, _):
            if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and not title.startswith("Default IME"):
                    try:
                        _, pid = win32gui.GetWindowThreadProcessId(hwnd)
                        if target_name in win32gui.GetWindowText(hwnd).lower():
                            windows.append(hwnd)
                    except:
                        pass
            return True
        
        win32gui.EnumWindows(callback, None)
        return windows 
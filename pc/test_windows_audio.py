import psutil
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
import win32gui
import win32ui
import win32con
import win32process
from PIL import Image
import io
import logging
import time
import os
import win32api

# Custom filter to exclude COM pointer messages
class NoPointerFilter(logging.Filter):
    def filter(self, record):
        return not (
            "ptr=" in record.getMessage() or 
            "Release <POINTER" in record.getMessage() or
            "CoUninitialize" in record.getMessage()
        )

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Create handlers with the custom filter
console_handler = logging.StreamHandler()
console_handler.addFilter(NoPointerFilter())
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

file_handler = logging.FileHandler('audio_test.log')
file_handler.addFilter(NoPointerFilter())
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Remove any existing handlers and add our filtered handlers
logger.handlers.clear()
logger.addHandler(console_handler)
logger.addHandler(file_handler)

def get_process_name_without_exe(name):
    """Remove .exe from process name for better matching"""
    return name.lower().replace('.exe', '')

def get_window_icon(hwnd):
    """Get icon for a window handle"""
    try:
        if not win32gui.IsWindow(hwnd):
            logging.warning(f"Invalid window handle: {hwnd}")
            return None
            
        window_text = win32gui.GetWindowText(hwnd)
        logging.debug(f"Attempting to get icon for window: {window_text} (handle: {hwnd})")
        
        try:
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
                logging.debug(f"Got icon handle for {window_text}")
                try:
                    # Get screen DC
                    hdc = win32gui.GetDC(0)
                    
                    # Create memory DC
                    memdc = win32gui.CreateCompatibleDC(hdc)
                    
                    # Create bitmap
                    hbmp = win32gui.CreateCompatibleBitmap(hdc, 32, 32)
                    
                    # Select bitmap into DC
                    old_bitmap = win32gui.SelectObject(memdc, hbmp)
                    
                    # Fill background with white
                    brush = win32gui.CreateSolidBrush(win32api.RGB(255, 255, 255))
                    win32gui.FillRect(memdc, (0, 0, 32, 32), brush)
                    
                    # Draw the icon
                    win32gui.DrawIconEx(memdc, 0, 0, hicon, 32, 32, 0, None, win32con.DI_NORMAL)
                    
                    # Get bitmap bits using win32ui
                    bmp = win32ui.CreateBitmapFromHandle(hbmp)
                    bmpstr = bmp.GetBitmapBits(True)
                    
                    # Convert to PIL Image
                    img = Image.frombuffer(
                        'RGBA',
                        (32, 32),
                        bmpstr,
                        'raw',
                        'BGRA',
                        0,
                        1
                    )
                    
                    # Clean up
                    win32gui.SelectObject(memdc, old_bitmap)
                    win32gui.DeleteObject(hbmp)
                    win32gui.DeleteObject(brush)
                    win32gui.DeleteDC(memdc)
                    win32gui.ReleaseDC(0, hdc)
                    win32gui.DestroyIcon(hicon)
                    
                    # Convert to PNG bytes
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    img_byte_arr.seek(0)
                    logging.info(f"Successfully converted icon to PNG for {window_text}")
                    return img_byte_arr.getvalue()
                    
                except Exception as e:
                    logging.error(f"Error converting icon to image for {window_text}: {e}")
                    try:
                        win32gui.DestroyIcon(hicon)
                    except:
                        pass
                    
            else:
                logging.debug(f"No icon found for window {window_text}")
                
        except Exception as e:
            logging.debug(f"Error getting window icon: {e}")
            
    except Exception as e:
        logging.error(f"Could not get icon for window: {e}")
    return None

def find_process_windows(process_name):
    """Find all windows belonging to processes with the given name"""
    windows = []
    target_name = get_process_name_without_exe(process_name)
    
    def callback(hwnd, _):
        if win32gui.IsWindow(hwnd) and win32gui.GetWindowText(hwnd):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process = psutil.Process(pid)
                if get_process_name_without_exe(process.name()) == target_name:
                    is_visible = win32gui.IsWindowVisible(hwnd)
                    title = win32gui.GetWindowText(hwnd)
                    if title and not title.startswith("Default IME") and not title.startswith("MSCTFIME"):
                        windows.append((hwnd, title, is_visible))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return True
    
    win32gui.EnumWindows(callback, None)
    return windows

def get_application_info():
    """Get information about all audio sessions including window icons"""
    sessions = AudioUtilities.GetAllSessions()
    app_info = []
    
    for session in sessions:
        try:
            if session.Process and session.Process.name():
                volume = session.SimpleAudioVolume
                vol_level = volume.GetMasterVolume()
                muted = volume.GetMute()
                
                # Get process info
                process_name = session.Process.name()
                pid = session.Process.pid
                process = psutil.Process(pid)
                
                logging.info(f"\nLooking for windows for {process_name}")
                
                # Find all windows for this process name
                windows = find_process_windows(process_name)
                
                # Get icon if we found any windows
                icon_data = None
                window_title = None
                
                if windows:
                    logging.info(f"Found {len(windows)} windows for {process_name}")
                    # Try visible windows first
                    visible_windows = [w for w in windows if w[2]]
                    windows_to_try = visible_windows if visible_windows else windows
                    
                    for hwnd, title, is_visible in windows_to_try:
                        logging.debug(f"Trying to get icon for window: {title} (Visible: {is_visible})")
                        icon_data = get_window_icon(hwnd)
                        if icon_data:
                            window_title = title
                            logging.info(f"Successfully got icon for {title}")
                            break
                else:
                    logging.debug(f"No windows found for {process_name}")
                
                info = {
                    "name": process_name,
                    "pid": pid,
                    "volume": int(vol_level * 100),
                    "muted": muted,
                    "icon_data": icon_data,
                    "has_icon": icon_data is not None,
                    "window_title": window_title,
                    "path": process.exe()
                }
                
                app_info.append(info)
                
        except Exception as e:
            logging.error(f"Error getting info for session: {e}")
    
    return app_info

def save_icon_to_file(icon_data, filename):
    """Save icon data to a PNG file"""
    if icon_data:
        with open(filename, 'wb') as f:
            f.write(icon_data)
        logging.info(f"Saved icon to {filename}")

def main():
    """Main function to test Windows audio functionality"""
    logging.info("Starting Windows audio test")
    
    # Create icons directory if it doesn't exist
    icons_dir = "icons"
    if not os.path.exists(icons_dir):
        os.makedirs(icons_dir)
    
    try:
        app_info = get_application_info()
        
        logging.info(f"\nFound {len(app_info)} applications with audio sessions:")
        for app in app_info:
            logging.info(f"\nApplication: {app['name']}")
            logging.info(f"  PID: {app['pid']}")
            logging.info(f"  Volume: {app['volume']}%")
            logging.info(f"  Muted: {app['muted']}")
            logging.info(f"  Has Icon: {app['has_icon']}")
            logging.info(f"  Icon Data Size: {len(app['icon_data']) if app['icon_data'] else 0} bytes")
            logging.info(f"  Window Title: {app['window_title']}")
            logging.info(f"  Path: {app['path']}")
            
            # Save icon if available
            if app['icon_data']:
                safe_name = "".join(x for x in app['name'] if x.isalnum())
                icon_path = os.path.join(icons_dir, f"{safe_name}_{app['pid']}.png")
                save_icon_to_file(app['icon_data'], icon_path)
        
        logging.info("\nIcons have been saved to the 'icons' directory")
            
    except KeyboardInterrupt:
        logging.info("\nTest stopped by user")

if __name__ == "__main__":
    main() 
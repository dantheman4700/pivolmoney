from machine import Pin, SPI, I2C, PWM
import time
import gc
from core.logger import get_logger
from core.config import (
    UIState, COLOR_BLACK, COLOR_WHITE, COLOR_GRAY, COLOR_DARK_GRAY,
    COLOR_RED, DISPLAY_WIDTH, DISPLAY_HEIGHT, LEFT_PANEL_WIDTH,
    RIGHT_PANEL_WIDTH, ICON_SIZE, ICON_SPACING, GRID_COLS, GRID_ROWS,
    PIN_SPI_SCK, PIN_SPI_MOSI, PIN_SPI_MISO, PIN_DC, PIN_RST,
    PIN_CS, PIN_LED, PIN_TOUCH_SDA, PIN_TOUCH_SCL, PIN_TOUCH_INT,
    PIN_TOUCH_RST, SPI_BAUDRATE, TOUCH_I2C_FREQ
)
from drivers.ili9488 import ILI9488
from drivers.ft6236 import FT6236

class UIManager:
    def __init__(self):
        self.logger = get_logger()
        self.display = None
        self.touch = None
        self.led_pwm = None
        self.current_state = UIState.BOOT
        self.apps = {}
        self.selected_app = None
        self.current_page = 0
        self.is_dragging = False
        self.drag_start_x = 0
        self.last_x = 0
        self.last_y = 0
        self.display_on = True
        self.current_brightness = 65535
        self.swipe_threshold = 50
        self.touch_callback = None
        self.encoder_callback = None
        
    def initialize_hardware(self):
        """Initialize display and touch hardware"""
        try:
            # Initialize LED backlight with PWM
            self.led_pwm = PWM(Pin(PIN_LED))
            self.led_pwm.freq(1000)
            self.led_pwm.duty_u16(self.current_brightness)
            
            # Initialize SPI for display
            spi = SPI(0,
                     baudrate=SPI_BAUDRATE,
                     polarity=0,
                     phase=0,
                     bits=8,
                     firstbit=SPI.MSB,
                     sck=Pin(PIN_SPI_SCK),
                     mosi=Pin(PIN_SPI_MOSI),
                     miso=Pin(PIN_SPI_MISO))
            
            # Initialize display
            self.logger.info("Resetting display...")
            self.display = ILI9488(
                spi,
                dc=Pin(PIN_DC, Pin.OUT),
                cs=Pin(PIN_CS, Pin.OUT),
                rst=Pin(PIN_RST, Pin.OUT)
            )
            
            # Reset and initialize display
            self.display.init()
            self.logger.info("Reset complete")
            
            # Initialize touch controller
            rst_pin = Pin(PIN_TOUCH_RST, Pin.OUT)
            rst_pin.value(0)
            time.sleep_ms(10)
            rst_pin.value(1)
            time.sleep_ms(300)
            
            i2c = I2C(0,
                     sda=Pin(PIN_TOUCH_SDA),
                     scl=Pin(PIN_TOUCH_SCL),
                     freq=TOUCH_I2C_FREQ)
            
            self.touch = FT6236(i2c, PIN_TOUCH_SDA, PIN_TOUCH_SCL)
            
            # Clear screen and draw initial UI
            self.clear_screen()
            self.draw_ui()
            
            self.logger.info("Hardware initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Hardware initialization failed: {str(e)}")
            return False
            
    def set_brightness(self, brightness):
        """Set display brightness"""
        self.current_brightness = max(0, min(65535, brightness))
        if self.display_on:
            self.led_pwm.duty_u16(self.current_brightness)
            
    def toggle_display(self):
        """Toggle display on/off"""
        self.display_on = not self.display_on
        self.led_pwm.duty_u16(self.current_brightness if self.display_on else 0)
        
    def set_state(self, state):
        """Set UI state and update display"""
        if state != self.current_state:
            self.current_state = state
            self.logger.info(f"UI state changed to: {state}")
            self.clear_screen()
            self.draw_ui()
            gc.collect()  # Clean up memory after UI update
            
    def clear_screen(self):
        """Clear the entire screen"""
        self.display.fill(COLOR_BLACK)
        
    def draw_ui(self):
        """Draw UI based on current state"""
        if self.current_state == UIState.BOOT:
            self.draw_boot_screen()
        elif self.current_state == UIState.CONNECTING:
            self.draw_connecting_screen()
        elif self.current_state == UIState.SIMPLE_MEDIA:
            self.draw_simple_media_ui()
        elif self.current_state == UIState.FULL_UI:
            self.draw_full_ui()
        elif self.current_state == UIState.ERROR:
            self.draw_error_screen()
            
    def draw_boot_screen(self):
        """Draw boot/waiting screen"""
        self.display.draw_text(
            DISPLAY_WIDTH//2 - 60,
            DISPLAY_HEIGHT//2 - 8,
            "Press BOOTSEL to start",
            COLOR_WHITE,
            None,
            scale=1
        )
        
    def draw_connecting_screen(self):
        """Draw connecting screen"""
        self.display.draw_text(
            DISPLAY_WIDTH//2 - 50,
            DISPLAY_HEIGHT//2 - 8,
            "Connecting to PC...",
            COLOR_WHITE,
            None,
            scale=1
        )
        
    def draw_error_screen(self):
        """Draw error screen"""
        self.display.draw_text(
            DISPLAY_WIDTH//2 - 40,
            DISPLAY_HEIGHT//2 - 16,
            "Error",
            COLOR_RED,
            None,
            scale=2
        )
        
    def draw_simple_media_ui(self):
        """Draw simple media control UI"""
        # Define button dimensions
        side_width = 100
        center_width = DISPLAY_WIDTH - (2 * side_width)
        center_height = DISPLAY_HEIGHT // 2
        
        # Draw Previous button
        self.draw_button('prev', 0, 0, side_width, DISPLAY_HEIGHT, "PREV")
        
        # Draw Mute button (top center)
        self.draw_button('mute', side_width, 0, center_width, center_height, "MUTE")
        
        # Draw Play button (bottom center)
        self.draw_button('play', side_width, center_height, center_width, center_height, "PLAY")
        
        # Draw Next button
        self.draw_button('next', DISPLAY_WIDTH - side_width, 0, side_width, DISPLAY_HEIGHT, "NEXT")
        
    def draw_full_ui(self):
        """Draw full UI with app list"""
        # Draw panel divider
        self.display.draw_vline(LEFT_PANEL_WIDTH, 0, DISPLAY_HEIGHT, COLOR_WHITE)
        
        # Draw app list
        self.draw_app_list()
        
        # Draw right panel for selected app
        if self.selected_app and self.selected_app in self.apps:
            self.draw_right_panel(self.apps[self.selected_app])
            
        # Draw control buttons
        self.draw_control_buttons()
        
    def draw_button(self, button_id, x, y, width, height, text, highlighted=False):
        """Draw a single button"""
        color = COLOR_GRAY if highlighted else COLOR_DARK_GRAY
        self.display.fill_rect(x, y, width, height, color)
        self.display.draw_rectangle(x, y, width, height, COLOR_WHITE)
        
        text_width = len(text) * 16  # Scale 2 font is 16 pixels wide per character
        text_x = x + (width - text_width) // 2
        text_y = y + (height - 16) // 2  # Scale 2 font is 16 pixels high
        
        text_color = COLOR_BLACK if highlighted else COLOR_WHITE
        self.display.draw_text(text_x, text_y, text, text_color, None, scale=2)
        
    def draw_app_list(self):
        """Draw app grid with icons"""
        # Clear left panel
        self.display.fill_rect(0, 0, LEFT_PANEL_WIDTH, DISPLAY_HEIGHT, COLOR_BLACK)
        
        # Draw Switch Device button at top
        button_height = 30
        button_width = LEFT_PANEL_WIDTH - 10
        self.draw_button('switch', 5, 5, button_width, button_height, "Switch Device")
        
        # Calculate grid layout
        usable_width = LEFT_PANEL_WIDTH - (GRID_COLS + 1) * ICON_SPACING
        usable_height = DISPLAY_HEIGHT - (GRID_ROWS + 1) * ICON_SPACING - 40 - button_height
        
        # Calculate icon positions
        start_x = (LEFT_PANEL_WIDTH - (GRID_COLS * ICON_WIDTH + (GRID_COLS - 1) * ICON_SPACING)) // 2
        start_y = button_height + 20 + (DISPLAY_HEIGHT - button_height - 40 - (GRID_ROWS * ICON_HEIGHT + (GRID_ROWS - 1) * ICON_SPACING)) // 2
        
        # Calculate page info
        items_per_page = GRID_COLS * GRID_ROWS
        total_pages = (len(self.apps) + items_per_page - 1) // items_per_page
        start_index = self.current_page * items_per_page
        
        # Draw apps for current page
        app_list = list(self.apps.items())
        for i in range(items_per_page):
            app_index = start_index + i
            if app_index >= len(app_list):
                break
                
            app_name, app_data = app_list[app_index]
            
            # Calculate grid position
            row = i // GRID_COLS
            col = i % GRID_COLS
            
            # Calculate pixel position
            x = start_x + col * (ICON_WIDTH + ICON_SPACING)
            y = start_y + row * (ICON_HEIGHT + ICON_SPACING)
            
            # Draw icon background
            if app_name == self.selected_app:
                self.display.fill_rect(x, y, ICON_WIDTH, ICON_HEIGHT, COLOR_GRAY)
                text_color = COLOR_BLACK
            else:
                self.display.fill_rect(x, y, ICON_WIDTH, ICON_HEIGHT, COLOR_DARK_GRAY)
                text_color = COLOR_WHITE
            
            # Draw icon if available
            if "icon" in app_data:
                try:
                    self.display.draw_icon(x, y, app_data["icon"], ICON_WIDTH, ICON_HEIGHT)
                except Exception as e:
                    self.logger.error(f"Error drawing icon for {app_name}: {str(e)}")
            
            # Draw app name
            text = app_name
            if len(text) > 8:
                text = text[:7] + '.'
            text_width = len(text) * 6
            text_x = x + (ICON_WIDTH - text_width) // 2
            self.display.draw_text(text_x, y + ICON_HEIGHT + 2, text, text_color, None)
        
        # Draw page indicator dots
        self.draw_page_indicators(total_pages)
        
    def draw_page_indicators(self, total_pages):
        """Draw page indicator dots"""
        dot_radius = 3
        dot_spacing = 10
        total_width = (total_pages * (dot_radius * 2 + dot_spacing)) - dot_spacing
        start_x = (LEFT_PANEL_WIDTH - total_width) // 2
        dot_y = DISPLAY_HEIGHT - 15
        
        for i in range(total_pages):
            dot_x = start_x + i * (dot_radius * 2 + dot_spacing)
            if i == self.current_page:
                self.display.fill_circle(dot_x + dot_radius, dot_y, dot_radius, COLOR_WHITE)
            else:
                self.display.fill_circle(dot_x + dot_radius, dot_y, dot_radius, COLOR_DARK_GRAY)
                
    def draw_right_panel(self, app_data):
        """Draw right panel with app info and volume"""
        # Clear right panel
        self.display.fill_rect(LEFT_PANEL_WIDTH + 1, 0, RIGHT_PANEL_WIDTH - 100, DISPLAY_HEIGHT, COLOR_BLACK)
        
        # Draw app name
        self.display.draw_text(
            LEFT_PANEL_WIDTH + 20,
            20,
            app_data.get("name", "Unknown"),
            COLOR_WHITE,
            None,
            scale=3
        )
        
        # Draw app icon if available
        if "icon" in app_data:
            try:
                icon_size = 60  # Fixed size for right panel icon
                icon_x = LEFT_PANEL_WIDTH + 20
                icon_y = 60
                self.display.draw_icon(icon_x, icon_y, app_data["icon"], icon_size, icon_size)
            except Exception as e:
                self.logger.error(f"Error drawing icon in right panel: {str(e)}")
        
        # Draw volume
        volume = app_data.get("volume", 0)
        self.display.draw_text(
            LEFT_PANEL_WIDTH + 20,
            140,  # Adjusted position to make room for icon
            str(volume),
            COLOR_WHITE,
            None,
            scale=4
        )
        
        # Draw volume bar
        bar_width = RIGHT_PANEL_WIDTH - 150
        bar_height = 20
        x = LEFT_PANEL_WIDTH + 20
        y = 200  # Adjusted position to make room for icon
        self.display.draw_rectangle(x, y, bar_width, bar_height, COLOR_WHITE)
        fill_width = int(bar_width * volume / 100)
        if fill_width > 0:
            self.display.fill_rect(x + 1, y + 1, fill_width - 2, bar_height - 2, COLOR_WHITE)
            
    def draw_control_buttons(self):
        """Draw media control and mute buttons"""
        button_panel_width = 100
        button_panel_x = DISPLAY_WIDTH - button_panel_width
        button_width = button_panel_width - 10
        button_height = DISPLAY_HEIGHT // 2 - 5
        
        # Draw vertical divider
        self.display.draw_vline(button_panel_x, 0, DISPLAY_HEIGHT, COLOR_WHITE)
        
        # Draw Mute button
        self.draw_button('mute', button_panel_x + 5, 5, button_width, button_height, "Mute")
        
        # Draw Mic button
        self.draw_button('mic', button_panel_x + 5, button_height + 10, button_width, button_height, "Mic")
        
    def handle_touch(self, x=None, y=None, action=None):
        """Handle touch events"""
        try:
            # If x and y are not provided, read from touch controller
            if x is None or y is None:
                touched, raw_x, raw_y = self.touch.read_touch()
                if touched:
                    # Convert touch coordinates
                    x = max(0, min(DISPLAY_WIDTH, 480 - int(raw_y)))
                    y = max(0, min(DISPLAY_HEIGHT, int(raw_x)))
                    
                    self.last_x = x
                    self.last_y = y
                    self.logger.debug(f"Touch detected at x={x}, y={y}")
                    
                    # Handle touch based on current UI state
                    if self.current_state == UIState.SIMPLE_MEDIA:
                        self.handle_simple_media_touch(x, y)
                    elif self.current_state == UIState.FULL_UI:
                        self.handle_full_ui_touch(x, y)
                        
            # If coordinates are provided directly (from callback)
            elif self.touch_callback:
                self.touch_callback(x, y, action)
                
        except Exception as e:
            self.logger.error(f"Touch handling error: {str(e)}")
            
    def handle_simple_media_touch(self, x, y):
        """Handle touch events for simple media UI"""
        side_width = 100
        center_height = DISPLAY_HEIGHT // 2
        
        if x < side_width:  # Previous button
            self.logger.debug("Previous button pressed")
            self.highlight_button('prev')
            if self.touch_callback:
                self.touch_callback(x, y, 'prev')
        elif x >= DISPLAY_WIDTH - side_width:  # Next button
            self.logger.debug("Next button pressed")
            self.highlight_button('next')
            if self.touch_callback:
                self.touch_callback(x, y, 'next')
        elif side_width <= x < DISPLAY_WIDTH - side_width:
            if y < center_height:  # Mute button
                self.logger.debug("Mute button pressed")
                self.highlight_button('mute')
                if self.touch_callback:
                    self.touch_callback(x, y, 'mute')
            else:  # Play button
                self.logger.debug("Play button pressed")
                self.highlight_button('play')
                if self.touch_callback:
                    self.touch_callback(x, y, 'play')
                    
    def handle_full_ui_touch(self, x, y):
        """Handle touch events for full UI"""
        if x < LEFT_PANEL_WIDTH:
            self.handle_app_list_touch(x, y)
        else:
            self.handle_control_touch(x, y)
            
    def handle_app_list_touch(self, x, y):
        """Handle touch events in app list area"""
        # Handle Switch Device button
        button_height = 30
        if y < button_height + 10:
            if self.touch_callback:
                self.touch_callback('switch')
            return
            
        if not self.is_dragging:
            self.is_dragging = True
            self.drag_start_x = x
        else:
            # Calculate drag distance
            drag_distance = x - self.drag_start_x
            
            # Check for swipe
            if abs(drag_distance) > self.swipe_threshold:
                items_per_page = GRID_COLS * GRID_ROWS
                total_pages = (len(self.apps) + items_per_page - 1) // items_per_page
                
                if drag_distance > 0 and self.current_page > 0:
                    self.current_page -= 1
                    self.draw_app_list()
                elif drag_distance < 0 and self.current_page < total_pages - 1:
                    self.current_page += 1
                    self.draw_app_list()
                self.is_dragging = False
                
    def handle_control_touch(self, x, y):
        """Handle touch events in control area"""
        button_panel_width = 100
        button_height = DISPLAY_HEIGHT // 2
        
        if x >= DISPLAY_WIDTH - button_panel_width:
            if y < button_height:
                self.highlight_button('mute')
                if self.touch_callback:
                    self.touch_callback('mute')
            else:
                self.highlight_button('mic')
                if self.touch_callback:
                    self.touch_callback('mic')
                    
    def handle_drag_end(self):
        """Handle end of drag gesture"""
        self.is_dragging = False
        if abs(self.drag_start_x - self.last_x) < self.swipe_threshold:
            # This was a tap, not a drag
            self.handle_app_tap(self.last_x, self.last_y)
            
    def handle_app_tap(self, x, y):
        """Handle app selection tap"""
        if x >= LEFT_PANEL_WIDTH:
            return
            
        # Calculate grid position
        items_per_page = GRID_COLS * GRID_ROWS
        start_index = self.current_page * items_per_page
        
        # Calculate which icon was tapped
        usable_width = LEFT_PANEL_WIDTH - (GRID_COLS + 1) * ICON_SPACING
        usable_height = DISPLAY_HEIGHT - (GRID_ROWS + 1) * ICON_SPACING - 60
        icon_width = usable_width // GRID_COLS
        icon_height = usable_height // GRID_ROWS
        
        col = (x - (LEFT_PANEL_WIDTH - usable_width) // 2) // (icon_width + ICON_SPACING)
        row = (y - 40) // (icon_height + ICON_SPACING)
        
        if 0 <= col < GRID_COLS and 0 <= row < GRID_ROWS:
            tapped_index = start_index + row * GRID_COLS + col
            app_list = list(self.apps.keys())
            if 0 <= tapped_index < len(app_list):
                self.selected_app = app_list[tapped_index]
                self.draw_full_ui()
                if self.touch_callback:
                    self.touch_callback('app_selected', self.selected_app)
                    
    def highlight_button(self, button_id):
        """Temporarily highlight a button"""
        if self.current_state == UIState.SIMPLE_MEDIA:
            self.draw_simple_media_ui()  # Redraw all buttons
            # Highlight specific button based on ID
            side_width = 100
            center_width = DISPLAY_WIDTH - (2 * side_width)
            center_height = DISPLAY_HEIGHT // 2
            
            if button_id == 'prev':
                self.draw_button('prev', 0, 0, side_width, DISPLAY_HEIGHT, "PREV", True)
            elif button_id == 'next':
                self.draw_button('next', DISPLAY_WIDTH - side_width, 0, side_width, DISPLAY_HEIGHT, "NEXT", True)
            elif button_id == 'mute':
                self.draw_button('mute', side_width, 0, center_width, center_height, "MUTE", True)
            elif button_id == 'play':
                self.draw_button('play', side_width, center_height, center_width, center_height, "PLAY", True)
                
        time.sleep_ms(100)  # Visual feedback duration
        self.draw_ui()  # Restore normal appearance
        
    def register_touch_callback(self, callback):
        """Register callback for touch events"""
        self.touch_callback = callback
        
    def register_encoder_callback(self, callback):
        """Register callback for encoder events"""
        self.encoder_callback = callback
        
    def update(self):
        """Update the UI state"""
        if self.display:
            self.display.update()
            
    def cleanup(self):
        """Cleanup UI resources"""
        try:
            if self.display:
                self.display.cleanup()
        except Exception as e:
            self.logger.error(f"UI cleanup error: {str(e)}")
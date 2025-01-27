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
    PIN_TOUCH_RST, SPI_BAUDRATE, TOUCH_I2C_FREQ, CENTER_PANEL_WIDTH,
    PIN_ROT_CLK, PIN_ROT_DT, PIN_ROT_SW
)
from drivers.ili9488 import ILI9488
from drivers.ft6236 import FT6236
from drivers.rotary import RotaryEncoder

class UIManager:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        return cls._instance
        
    def __init__(self):
        if UIManager._instance is not None:
            raise Exception("UIManager is a singleton!")
        UIManager._instance = self
        self.logger = get_logger()
        self.display = None
        self.touch = None
        self.encoder = None
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
        self.last_volume_update = time.ticks_ms()
        self.volume_update_delay = 50  # 50ms between volume updates
        
    def initialize_hardware(self):
        """Initialize display and touch hardware"""
        try:
            # Initialize LED backlight with PWM
            self.led_pwm = PWM(Pin(PIN_LED))
            self.led_pwm.freq(1000)
            self.led_pwm.duty_u16(self.current_brightness)
            
            # Initialize SPI for display
            spi = SPI(1,
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
            
            # Initialize rotary encoder
            self.encoder = RotaryEncoder(
                PIN_ROT_CLK,
                PIN_ROT_DT,
                PIN_ROT_SW,
                min_val=0,
                max_val=100,
                step=1
            )
            
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
        # Clear screen first
        self.display.fill(COLOR_BLACK)
        
        # Draw panel dividers (two vertical lines)
        self.display.draw_vline(LEFT_PANEL_WIDTH, 0, DISPLAY_HEIGHT, COLOR_WHITE)
        self.display.draw_vline(DISPLAY_WIDTH - RIGHT_PANEL_WIDTH, 0, DISPLAY_HEIGHT, COLOR_WHITE)
        
        # Draw app list with Switch Device button
        self.draw_app_list()
        
        # Draw center panel with app info
        if self.selected_app and self.selected_app in self.apps:
            app_data = self.apps[self.selected_app]
            self.draw_center_panel(self.selected_app, app_data.get("volume", 0))
        elif self.selected_app == "Master":
            self.draw_center_panel("Master", 100)
        else:
            # Draw empty center panel with just media controls
            self.draw_center_panel("Select App", 0)
        
        # Draw right panel buttons (Mute/Mic)
        self.draw_side_buttons()
        
    def draw_app_list(self):
        """Draw app grid with icons"""
        # Clear left panel
        self.display.fill_rect(0, 0, LEFT_PANEL_WIDTH, DISPLAY_HEIGHT, COLOR_BLACK)
        
        # Draw Switch Device button at top (centered text)
        button_height = 30
        button_width = LEFT_PANEL_WIDTH - 10
        # Using similar ratio as media buttons (about 8-9 pixels per char)
        text_width = 110  # "Switch Device" (12 chars * 8.5 pixels)
        button_x = 5
        text_x = button_x + (button_width - text_width) // 2
        self.display.fill_rect(button_x, 5, button_width, button_height, COLOR_DARK_GRAY)
        self.display.draw_text(text_x, 5 + (button_height - 8) // 2, "Switch Device", COLOR_WHITE, None)
        
        # Calculate grid layout for 2x3 grid
        start_x = 10  # Fixed left margin
        start_y = button_height + 20  # Start below Switch Device button
        
        # Add master volume as first item
        app_list = [("Master", {"name": "Master", "volume": 100})] + list(self.apps.items())
        
        # Draw apps
        for i, (app_name, app_data) in enumerate(app_list):
            if i >= GRID_COLS * GRID_ROWS:
                break
                
            # Calculate grid position
            row = i // GRID_COLS
            col = i % GRID_COLS
            
            # Calculate pixel position
            x = start_x + col * (ICON_SIZE + ICON_SPACING)
            y = start_y + row * (ICON_SIZE + ICON_SPACING + 15)  # Extra space for text
            
            # Draw icon background
            if app_name == self.selected_app:
                self.display.fill_rect(x, y, ICON_SIZE, ICON_SIZE, COLOR_GRAY)
                # Don't draw text for selected app
            else:
                self.display.fill_rect(x, y, ICON_SIZE, ICON_SIZE, COLOR_DARK_GRAY)
                # Draw app name (remove .exe and truncate if needed)
                text = app_name
                if text.lower().endswith('.exe'):
                    text = text[:-4]
                if len(text) > 8:
                    text = text[:7] + '.'
                    
                # Calculate text width using 8 pixels per char
                text_width = len(text) * 8
                # Center text under icon
                text_x = x + ((ICON_SIZE - text_width) // 2) - 2
                text_y = y + ICON_SIZE + 5
                self.display.draw_text(text_x, text_y, text, COLOR_WHITE, None)
            
            # Draw icon if available
            if app_name != "Master" and "icon" in app_data:
                try:
                    # Center the 48x48 icon in the 60x60 space
                    icon_offset = (ICON_SIZE - 48) // 2
                    self.display.draw_icon(x + icon_offset, y + icon_offset, app_data["icon"])
                except Exception as e:
                    self.logger.error(f"Error drawing icon for {app_name}: {str(e)}")
        
    def draw_center_panel(self, app_name, volume):
        """Draw center panel with app name and volume"""
        panel_width = CENTER_PANEL_WIDTH
        panel_start_x = LEFT_PANEL_WIDTH + 1
        
        # Clear center panel
        self.display.fill_rect(panel_start_x, 0, panel_width - 1, DISPLAY_HEIGHT, COLOR_BLACK)
        
        # Calculate available height (excluding media controls area)
        media_section_height = 60
        available_height = DISPLAY_HEIGHT - media_section_height
        
        # Process app name - remove .exe extension first
        if app_name.lower().endswith('.exe'):
            app_name = app_name[:-4]  # Strip .exe extension
        
        # Split into lines of maximum 11 characters
        CHARS_PER_LINE = 11
        lines = []
        remaining_text = app_name
        
        while remaining_text:
            if len(remaining_text) <= CHARS_PER_LINE:
                lines.append(remaining_text)
                break
            else:
                lines.append(remaining_text[:CHARS_PER_LINE])
                remaining_text = remaining_text[CHARS_PER_LINE:]
        
        # Limit to 3 lines maximum
        if len(lines) > 3:
            lines = lines[:2]
            lines[1] = lines[1][:8] + "..."  # Adjusted for 11 char limit
        
        # Calculate text block height and starting position
        line_height = 25  # Height of each line at scale 2
        total_text_height = len(lines) * line_height
        text_start_y = 20  # Fixed padding from top
        text_start_x = panel_start_x + 10  # Fixed left margin
        
        # Draw each line left-aligned
        for i, line in enumerate(lines):
            self.display.draw_text(text_start_x, text_start_y + (i * line_height), line, COLOR_WHITE, None, scale=2)
        
        # Draw volume (scaled x4) - left aligned like the text
        volume_str = str(volume)
        volume_y = text_start_y + total_text_height + 30  # Fixed spacing after text
        self.display.draw_text(text_start_x, volume_y, volume_str, COLOR_WHITE, None, scale=4)
        
        # Draw dividing line above media controls
        self.display.draw_hline(panel_start_x, DISPLAY_HEIGHT - media_section_height, panel_width - 2, COLOR_WHITE)
        
        # Draw media controls at bottom
        self.draw_media_controls()
        
    def draw_media_controls(self, highlight_button=None):
        """Draw media control buttons"""
        panel_width = CENTER_PANEL_WIDTH
        panel_start_x = LEFT_PANEL_WIDTH + 1
        media_section_height = 60
        button_height = 45
        
        # Draw dividing line above media controls
        y_divider = DISPLAY_HEIGHT - media_section_height
        self.display.draw_hline(panel_start_x, y_divider, panel_width - 2, COLOR_WHITE)
        
        # Calculate button dimensions and positions
        button_width = (panel_width - 40) // 3  # Equal width for all three buttons
        button_y = y_divider + (media_section_height - button_height) // 2
        
        # Calculate x positions for buttons with spacing
        spacing = 10
        total_width = (button_width * 3) + (spacing * 2)
        start_x = panel_start_x + (panel_width - total_width) // 2
        
        prev_x = start_x
        play_x = start_x + button_width + spacing
        next_x = start_x + 2 * (button_width + spacing)
        
        # Draw Previous button
        color = COLOR_GRAY if highlight_button == 'prev' else COLOR_DARK_GRAY
        text_color = COLOR_BLACK if highlight_button == 'prev' else COLOR_WHITE
        self.display.fill_rect(prev_x, button_y, button_width, button_height, color)
        text_x = prev_x + (button_width - 30) // 2
        self.display.draw_text(text_x, button_y + (button_height - 8) // 2, "Prev", text_color, None)
        
        # Draw Play button
        color = COLOR_GRAY if highlight_button == 'play' else COLOR_DARK_GRAY
        text_color = COLOR_BLACK if highlight_button == 'play' else COLOR_WHITE
        self.display.fill_rect(play_x, button_y, button_width, button_height, color)
        text_x = play_x + (button_width - 36) // 2
        self.display.draw_text(text_x, button_y + (button_height - 8) // 2, "Play", text_color, None)
        
        # Draw Next button
        color = COLOR_GRAY if highlight_button == 'next' else COLOR_DARK_GRAY
        text_color = COLOR_BLACK if highlight_button == 'next' else COLOR_WHITE
        self.display.fill_rect(next_x, button_y, button_width, button_height, color)
        text_x = next_x + (button_width - 30) // 2
        self.display.draw_text(text_x, button_y + (button_height - 8) // 2, "Next", text_color, None)
        
    def draw_side_buttons(self):
        """Draw right side Mute/Mic buttons"""
        button_width = 90
        button_height = DISPLAY_HEIGHT // 2 - 5
        button_x = DISPLAY_WIDTH - 95
        
        # Draw Mute button
        self.draw_button('mute', button_x, 5, button_width, button_height, "Mute")
        
        # Draw Mic button
        self.draw_button('mic', button_x, button_height + 10, button_width, button_height, "Mic")
        
    def draw_button(self, button_id, x, y, width, height, text, highlighted=False):
        """Draw a single button"""
        color = COLOR_GRAY if highlighted else COLOR_DARK_GRAY
        self.display.fill_rect(x, y, width, height, color)
        
        text_color = COLOR_BLACK if highlighted else COLOR_WHITE
        text_width = len(text) * 6
        text_x = x + (width - text_width) // 2
        text_y = y + (height - 8) // 2
        
        self.display.draw_text(text_x, text_y, text, text_color, None)
        
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
                if action is None:
                    self.touch_callback(x, y)  # For regular touch events
                else:
                    self.touch_callback(action)  # For action-only events like 'switch', 'mute', etc.
                
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
                self.touch_callback('prev')  # Just send the action
        elif x >= DISPLAY_WIDTH - side_width:  # Next button
            self.logger.debug("Next button pressed")
            self.highlight_button('next')
            if self.touch_callback:
                self.touch_callback('next')  # Just send the action
        elif side_width <= x < DISPLAY_WIDTH - side_width:
            if y < center_height:  # Mute button
                self.logger.debug("Mute button pressed")
                self.highlight_button('mute')
                if self.touch_callback:
                    self.touch_callback('mute')  # Just send the action
            else:  # Play button
                self.logger.debug("Play button pressed")
                self.highlight_button('play')
                if self.touch_callback:
                    self.touch_callback('play')  # Just send the action
                    
    def handle_full_ui_touch(self, x, y):
        """Handle touch events in full UI mode"""
        # Check if touch is in left panel (app grid)
        if x < LEFT_PANEL_WIDTH:
            self.handle_app_list_touch(x, y)
            return
            
        # Check if touch is in right panel (buttons)
        if x > DISPLAY_WIDTH - 100:
            self.handle_side_button_touch(x, y)
            return
            
        # Check if touch is in media controls area
        if y > DISPLAY_HEIGHT - 60:
            self.handle_media_controls_touch(x, y)
            return
            
    def handle_media_controls_touch(self, x, y):
        """Handle touch events in media controls area"""
        panel_width = DISPLAY_WIDTH - LEFT_PANEL_WIDTH - RIGHT_PANEL_WIDTH
        media_section_height = 60
        button_height = 45
        
        # Calculate button dimensions and positions
        button_width = (panel_width - 40) // 3  # Equal width for all three buttons
        button_y = DISPLAY_HEIGHT - media_section_height + (media_section_height - button_height) // 2
        
        # Calculate x positions for buttons with spacing
        spacing = 10
        total_width = (button_width * 3) + (spacing * 2)
        start_x = LEFT_PANEL_WIDTH + (panel_width - total_width) // 2
        
        prev_x = start_x
        play_x = start_x + button_width + spacing
        next_x = start_x + 2 * (button_width + spacing)
        
        # Check which button was pressed
        if button_y <= y <= button_y + button_height:
            if prev_x <= x <= prev_x + button_width:
                self.logger.info("Previous track button pressed")
                if self.touch_callback:
                    self.touch_callback("prev")
                self.draw_media_controls("prev")
                time.sleep(0.1)
                self.draw_media_controls()
                
            elif play_x <= x <= play_x + button_width:
                self.logger.info("Play/Pause button pressed")
                if self.touch_callback:
                    self.touch_callback("play")
                self.draw_media_controls("play")
                time.sleep(0.1)
                self.draw_media_controls()
                
            elif next_x <= x <= next_x + button_width:
                self.logger.info("Next track button pressed")
                if self.touch_callback:
                    self.touch_callback("next")
                self.draw_media_controls("next")
                time.sleep(0.1)
                self.draw_media_controls()
                
    def handle_app_list_touch(self, x, y):
        """Handle touch events for app list"""
        # Check if touch is in Switch Device button
        if 5 <= x <= LEFT_PANEL_WIDTH - 5 and 5 <= y <= 35:
            self.logger.info("Switch Device button pressed")
            if self.touch_callback:
                self.touch_callback('switch')
            return

        # Calculate grid layout
        start_x = 10  # Fixed left margin
        start_y = 50  # Start below Switch Device button
        
        # Calculate grid cell size
        cell_width = ICON_SIZE + ICON_SPACING
        cell_height = ICON_SIZE + ICON_SPACING + 15  # Extra space for text
        
        # Check if touch is in grid area
        if (start_x <= x < start_x + GRID_COLS * cell_width and
            start_y <= y < start_y + GRID_ROWS * cell_height):
            
            # Calculate which icon was tapped
            col = (x - start_x) // cell_width
            row = (y - start_y) // cell_height
            
            if 0 <= col < GRID_COLS and 0 <= row < GRID_ROWS:
                tapped_index = row * GRID_COLS + col
                app_list = ["Master"] + list(self.apps.keys())
                if 0 <= tapped_index < len(app_list):
                    # Store previous selection
                    prev_app = self.selected_app
                    
                    # Update selection
                    self.selected_app = app_list[tapped_index]
                    self.logger.info(f"Selected app: {self.selected_app}")
                    
                    # Calculate positions for both previous and new selections
                    def get_app_position(app_name):
                        if app_name not in app_list:
                            return None
                        idx = app_list.index(app_name)
                        row = idx // GRID_COLS
                        col = idx % GRID_COLS
                        x = start_x + col * cell_width
                        y = start_y + row * cell_height
                        return (x, y)
                    
                    # Update previous selection if it exists
                    if prev_app:
                        prev_pos = get_app_position(prev_app)
                        if prev_pos:
                            x, y = prev_pos
                            # Draw unselected state
                            self.display.fill_rect(x, y, ICON_SIZE, ICON_SIZE, COLOR_DARK_GRAY)
                            # Draw app name
                            text = prev_app
                            if text.lower().endswith('.exe'):
                                text = text[:-4]
                            if len(text) > 8:
                                text = text[:7] + '.'
                            text_width = len(text) * 8
                            text_x = x + ((ICON_SIZE - text_width) // 2) - 2
                            text_y = y + ICON_SIZE + 5
                            self.display.draw_text(text_x, text_y, text, COLOR_WHITE, None)
                            # Draw icon if available
                            if prev_app != "Master" and "icon" in self.apps[prev_app]:
                                try:
                                    icon_offset = (ICON_SIZE - 48) // 2
                                    self.display.draw_icon(x + icon_offset, y + icon_offset, self.apps[prev_app]["icon"])
                                except Exception as e:
                                    self.logger.error(f"Error drawing icon for {prev_app}: {str(e)}")
                    
                    # Update new selection
                    new_pos = get_app_position(self.selected_app)
                    if new_pos:
                        x, y = new_pos
                        # Draw selected state
                        self.display.fill_rect(x, y, ICON_SIZE, ICON_SIZE, COLOR_GRAY)
                        # Draw icon if available
                        if self.selected_app != "Master" and "icon" in self.apps[self.selected_app]:
                            try:
                                icon_offset = (ICON_SIZE - 48) // 2
                                self.display.draw_icon(x + icon_offset, y + icon_offset, self.apps[self.selected_app]["icon"])
                            except Exception as e:
                                self.logger.error(f"Error drawing icon for {self.selected_app}: {str(e)}")
                    
                    # Update center panel
                    if self.selected_app == "Master":
                        self.draw_center_panel("Master", 100)
                    else:
                        app_data = self.apps[self.selected_app]
                        self.draw_center_panel(self.selected_app, app_data.get("volume", 0))
                    
                    if self.touch_callback:
                        self.touch_callback('app_selected', self.selected_app)
                    
    def handle_side_button_touch(self, x, y):
        """Handle touch events for side buttons"""
        button_width = 90
        button_height = DISPLAY_HEIGHT // 2 - 5
        button_x = DISPLAY_WIDTH - 95
        
        # Check if touch is in Mute button area
        if button_x <= x <= button_x + button_width and 5 <= y <= button_height:
            self.logger.info("Mute button pressed")
            if self.touch_callback:
                self.touch_callback('mute')
        # Check if touch is in Mic button area
        elif button_x <= x <= button_x + button_width and button_height + 10 <= y <= DISPLAY_HEIGHT - 5:
            self.logger.info("Mic button pressed")
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
        button_height = 30
        start_x = (LEFT_PANEL_WIDTH - (GRID_COLS * ICON_SIZE + (GRID_COLS - 1) * ICON_SPACING)) // 2
        start_y = button_height + 20 + (DISPLAY_HEIGHT - button_height - 40 - (GRID_ROWS * ICON_SIZE + (GRID_ROWS - 1) * ICON_SPACING)) // 2
        
        if start_x <= x < start_x + GRID_COLS * (ICON_SIZE + ICON_SPACING):
            col = (x - start_x) // (ICON_SIZE + ICON_SPACING)
            row = (y - start_y) // (ICON_SIZE + ICON_SPACING)
            
            if 0 <= col < GRID_COLS and 0 <= row < GRID_ROWS:
                tapped_index = start_index + row * GRID_COLS + col
                app_list = ["Master"] + list(self.apps.keys())
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
        # Handle any touch events
        self.handle_touch()
        
        # Handle encoder events
        if self.encoder and self.current_state == UIState.FULL_UI:
            value_changed, button_pressed = self.encoder.read()
            
            if value_changed and self.selected_app:
                current_time = time.ticks_ms()
                if time.ticks_diff(current_time, self.last_volume_update) >= self.volume_update_delay:
                    # Get current volume and send update
                    volume = self.encoder.get_value()
                    if self.encoder_callback:
                        self.encoder_callback('volume_change', self.selected_app, volume)
                    self.last_volume_update = current_time
            
            if button_pressed and self.selected_app:
                # Toggle mute for the selected app
                if self.encoder_callback:
                    self.encoder_callback('toggle_mute', self.selected_app)

    def handle_volume_update(self, app_name, volume):
        """Handle volume update from PC"""
        if app_name in self.apps:
            self.apps[app_name]["volume"] = volume
            # Update encoder value if this is the selected app
            if app_name == self.selected_app:
                self.encoder.set_value(volume)
            # Redraw center panel if this is the selected app
            if app_name == self.selected_app:
                self.draw_center_panel(app_name, volume)

    def handle_mute_update(self, app_name, muted):
        """Handle mute update from PC"""
        if app_name in self.apps:
            self.apps[app_name]["muted"] = muted
            # Redraw center panel if this is the selected app
            if app_name == self.selected_app:
                self.draw_center_panel(app_name, self.apps[app_name]["volume"])

    def cleanup(self):
        """Cleanup UI resources"""
        try:
            # Turn off display backlight
            if self.led_pwm:
                self.led_pwm.duty_u16(0)
        except Exception as e:
            self.logger.error(f"UI cleanup error: {str(e)}")

    def draw_app_icon(self, app_name, app_data, x, y, is_selected):
        """Draw a single app icon and name"""
        # Draw icon background
        if is_selected:
            self.display.fill_rect(x, y, ICON_SIZE, ICON_SIZE, COLOR_GRAY)
            text_color = COLOR_BLACK
        else:
            self.display.fill_rect(x, y, ICON_SIZE, ICON_SIZE, COLOR_DARK_GRAY)
            text_color = COLOR_WHITE
        
        # Draw icon if available
        if app_name != "Master" and "icon" in app_data:
            try:
                # Center the 48x48 icon in the 60x60 space
                icon_offset = (ICON_SIZE - 48) // 2
                self.display.draw_icon(x + icon_offset, y + icon_offset, app_data["icon"])
            except Exception as e:
                self.logger.error(f"Error drawing icon for {app_name}: {str(e)}")
        
        # Process and draw app name
        if app_name.lower().endswith('.exe'):
            text = app_name[:-4]  # Remove .exe extension
        else:
            text = app_name
            
        if len(text) > 8:
            text = text[:7] + '.'
        text_width = len(text) * 6
        text_x = x + (ICON_SIZE - text_width) // 2
        self.display.draw_text(text_x, y + ICON_SIZE + 5, text, text_color, None)
from machine import Pin, SPI, I2C, PWM
from ili9488 import ILI9488
from ft6236 import FT6236
from rotary import RotaryEncoder
import time

print("Initializing display and touch...")

# Initialize display
print("Starting UI test...")

# Display Pins
SPI_SCK = 18    # Pin 7 on LCD
SPI_MOSI = 19   # Pin 6 on LCD
SPI_MISO = 16   # Pin 9 on LCD
DC_PIN = 20     # Pin 5 on LCD
RST_PIN = 21    # Pin 4 on LCD
CS_PIN = 17     # Pin 3 on LCD
LED_PIN = 22    # Pin 8 on LCD

# Initialize LED backlight with PWM
led_pwm = PWM(Pin(LED_PIN))
led_pwm.freq(1000)  # Set PWM frequency to 1kHz
brightness = 65535  # Max brightness (16-bit PWM)
led_pwm.duty_u16(brightness)

# Initialize display pins
sck = Pin(SPI_SCK, Pin.OUT)
mosi = Pin(SPI_MOSI, Pin.OUT)
miso = Pin(SPI_MISO, Pin.IN)
dc = Pin(DC_PIN, Pin.OUT)
rst = Pin(RST_PIN, Pin.OUT)
cs = Pin(CS_PIN, Pin.OUT)

# Complete reset sequence
print("Performing complete reset sequence...")

# Rotary Encoder Pins
ROT_CLK = 14
ROT_DT = 15
ROT_SW = 13

# Screen dimensions
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320
LEFT_PANEL_WIDTH = 160  # Width of app list panel
RIGHT_PANEL_WIDTH = SCREEN_WIDTH - LEFT_PANEL_WIDTH

# Initialize SPI
spi = SPI(0,
          baudrate=62500000,   # Back to 62.5MHz for faster drawing
          polarity=0,
          phase=0,
          bits=8,
          firstbit=SPI.MSB,
          sck=Pin(SPI_SCK),
          mosi=Pin(SPI_MOSI),
          miso=Pin(SPI_MISO))

display = ILI9488(spi, dc=dc, cs=cs, rst=rst)

# Touch controller pins
TOUCH_SDA = 4   # GP4
TOUCH_SCL = 5   # GP5
TOUCH_INT = 6   # GP6
TOUCH_RST = 7   # GP7

# Initialize RST and INT pins
rst_pin = Pin(TOUCH_RST, Pin.OUT)
int_pin = Pin(TOUCH_INT, Pin.IN)

# Reset touch controller
print("Resetting touch controller...")
rst_pin.value(0)  # Reset active low
time.sleep_ms(10)
rst_pin.value(1)
time.sleep_ms(300)  # Wait for touch controller to initialize

# Initialize I2C
print("Initializing I2C...")
i2c = I2C(0, sda=Pin(TOUCH_SDA), scl=Pin(TOUCH_SCL), freq=100000)

# Initialize touch controller
touch = FT6236(i2c, TOUCH_SDA, TOUCH_SCL)

# Define colors (RGB565 format)
BLACK = 0x0000
WHITE = 0xFFFF
GREEN = 0x07E0
GRAY = 0x7BEF
DARK_GRAY = 0x39E7

# App list parameters
ICON_SIZE = 60  # Size of each app icon
ICON_SPACING = 10  # Space between icons
GRID_COLS = 2  # Number of columns
GRID_ROWS = 3  # Number of visible rows

print("Starting UI test...")

# Clear screen
print("Clearing screen...")
display.fill(BLACK)

# Draw panel divider
print("Drawing panel divider...")
display.draw_vline(LEFT_PANEL_WIDTH, 0, SCREEN_HEIGHT, WHITE)

# Sample apps for testing (including blank apps)
apps = [
    "Master",  # Add Master as first app
    "Spotify",
    "Chrome",
    "Discord",
    "Game",
    "Teams",
    "Firefox",
    "App 7",
    "App 8",
    "App 9",
    "App 10",
    "App 11",
    "App 12",
    "App 13",
    "App 14",
    "App 15"
]

# Scrolling variables
current_page = 0    # Current page number
is_dragging = False
drag_start_x = 0
SWIPE_THRESHOLD = 50  # Minimum pixels to trigger page change

# Initialize touch handling variables
last_touch_time = 0
TOUCH_DEBOUNCE_MS = 100  # 100ms debounce

# Initialize UI state variables
current_page = 0
is_dragging = False
drag_start_x = 0
selected_app = 0
last_x = 0
last_y = 0

# Draw app list (left panel)
def draw_app_list(selected_index=0):
    # Clear left panel
    display.fill_rect(0, 0, LEFT_PANEL_WIDTH, SCREEN_HEIGHT, BLACK)
    
    # Calculate grid layout
    usable_width = LEFT_PANEL_WIDTH - (GRID_COLS + 1) * ICON_SPACING
    usable_height = SCREEN_HEIGHT - (GRID_ROWS + 1) * ICON_SPACING - 20  # Leave space for page number
    icon_width = usable_width // GRID_COLS
    icon_height = usable_height // GRID_ROWS
    ICON_SIZE = min(icon_width, icon_height)  # Keep icons square
    
    # Calculate starting positions to center the grid
    start_x = (LEFT_PANEL_WIDTH - (GRID_COLS * ICON_SIZE + (GRID_COLS - 1) * ICON_SPACING)) // 2
    start_y = (SCREEN_HEIGHT - (GRID_ROWS * ICON_SIZE + (GRID_ROWS - 1) * ICON_SPACING) - 20) // 2
    
    # Calculate page info
    items_per_page = GRID_COLS * GRID_ROWS
    total_pages = (len(apps) + items_per_page - 1) // items_per_page
    start_index = current_page * items_per_page
    
    # Draw apps for current page
    for i in range(items_per_page):
        app_index = start_index + i
        if app_index >= len(apps):
            break
            
        # Calculate grid position
        row = i // GRID_COLS
        col = i % GRID_COLS
        
        # Calculate pixel position
        x = start_x + col * (ICON_SIZE + ICON_SPACING)
        y = start_y + row * (ICON_SIZE + ICON_SPACING)
        
        # Draw icon background
        if app_index == selected_app:
            display.fill_rect(x, y, ICON_SIZE, ICON_SIZE, GRAY)
            text_color = BLACK
        else:
            display.fill_rect(x, y, ICON_SIZE, ICON_SIZE, DARK_GRAY)
            text_color = WHITE
        
        # Draw app name (centered under icon)
        text = apps[app_index]
        if len(text) > 8:  # Truncate long names
            text = text[:7] + '.'
        text_width = len(text) * 6  # Assuming 6 pixels per character
        text_x = x + (ICON_SIZE - text_width) // 2
        display.draw_text(text_x, y + ICON_SIZE + 2, text, text_color, None)
    
    # Draw page number at bottom
    page_text = f"Page {current_page + 1}/{total_pages}"
    text_width = len(page_text) * 6
    text_x = (LEFT_PANEL_WIDTH - text_width) // 2
    display.draw_text(text_x, SCREEN_HEIGHT - 15, page_text, WHITE, None)

# Draw right panel info
def draw_right_panel(app_name, volume=75):
    print(f"Drawing right panel for app: {app_name}")
    
    # Define panel sections
    info_panel_width = RIGHT_PANEL_WIDTH - 100  # Main info area
    button_panel_width = 100  # Width for buttons column
    button_panel_x = SCREEN_WIDTH - button_panel_width
    
    # Clear only the info area
    display.fill_rect(LEFT_PANEL_WIDTH+1, 0, info_panel_width, SCREEN_HEIGHT, BLACK)
    
    # Draw vertical divider for button column
    display.draw_vline(button_panel_x, 0, SCREEN_HEIGHT, WHITE)
    
    # Draw app info in main area
    print("Drawing app name")
    display.draw_text(LEFT_PANEL_WIDTH+20, 20, app_name, WHITE, None, scale=3)
    
    print("Drawing volume")
    display.draw_text(LEFT_PANEL_WIDTH+20, 100, str(volume), WHITE, None, scale=4)

def draw_buttons(highlight_button=None):
    """Draw the Mute/Mic buttons. If highlight_button is 'mute' or 'mic', draw it highlighted"""
    button_panel_width = 100
    button_panel_x = SCREEN_WIDTH - button_panel_width
    button_width = button_panel_width - 10
    button_height = SCREEN_HEIGHT // 2 - 5
    button_x = button_panel_x + 5
    
    # Clear only the button area
    display.fill_rect(button_panel_x + 1, 0, button_panel_width - 1, SCREEN_HEIGHT, BLACK)
    
    # Mute button (top half)
    mute_color = GRAY if highlight_button == 'mute' else DARK_GRAY
    display.draw_button(button_x, 5, button_width, button_height, "Mute", WHITE, mute_color)
    
    # Mic button (bottom half)
    mic_color = GRAY if highlight_button == 'mic' else DARK_GRAY
    display.draw_button(button_x, button_height + 10, button_width, button_height, "Mic", WHITE, mic_color)

def handle_touch():
    global current_page, is_dragging, drag_start_x, selected_app, last_x, last_y
    
    touched, raw_x, raw_y = touch.read_touch()
    current_time = time.ticks_ms()
    
    if touched:
        # Touch coordinates are flipped and inverted:
        # - raw_y: 0 is right side, 320 is left side
        # - raw_x: 0 is top, 320 is bottom
        x = max(0, min(SCREEN_WIDTH, 480 - int(raw_y)))   # Flip and invert X
        y = max(0, min(SCREEN_HEIGHT, int(raw_x)))        # Y just needs scaling
        
        # Validate touch coordinates
        if x < 0 or x >= SCREEN_WIDTH or y < 0 or y >= SCREEN_HEIGHT:
            return
            
        last_x = x  # Store current position
        last_y = y
        print(f"\nTouch detected at x: {x}, y: {y}")  # Debug coordinates
        
        # Handle left panel touches (icon grid)
        if x < LEFT_PANEL_WIDTH:
            if not is_dragging:
                is_dragging = True
                drag_start_x = x
                print("Started dragging in left panel")
            else:
                # Calculate drag distance
                drag_distance = x - drag_start_x
                
                # Check for swipe
                if abs(drag_distance) > SWIPE_THRESHOLD:
                    items_per_page = GRID_COLS * GRID_ROWS
                    total_pages = (len(apps) + items_per_page - 1) // items_per_page
                    
                    if drag_distance > 0 and current_page > 0:  # Swipe right
                        current_page -= 1
                        print(f"Page changed to {current_page + 1}")
                        draw_app_list(selected_app)
                        is_dragging = False
                    elif drag_distance < 0 and current_page < total_pages - 1:  # Swipe left
                        current_page += 1
                        print(f"Page changed to {current_page + 1}")
                        draw_app_list(selected_app)
                        is_dragging = False
        
        # Handle right panel touches (buttons)
        else:
            button_panel_width = 100
            button_panel_x = SCREEN_WIDTH - button_panel_width
            
            # Only process touches in button column
            if x >= button_panel_x:
                button_height = SCREEN_HEIGHT // 2 - 5
                
                # Mute button (top half)
                if 5 <= y <= button_height:
                    print("MUTE BUTTON PRESSED")
                    # Add visual feedback
                    draw_buttons('mute')  # Highlight mute button
                    time.sleep_ms(100)
                    draw_buttons()  # Return to normal
                # Mic button (bottom half)
                elif button_height + 10 <= y <= SCREEN_HEIGHT - 5:
                    print("MIC BUTTON PRESSED")
                    # Add visual feedback
                    draw_buttons('mic')  # Highlight mic button
                    time.sleep_ms(100)
                    draw_buttons()  # Return to normal
    
    # Handle touch release
    elif is_dragging:
        is_dragging = False
        # Handle tap (if we haven't dragged much)
        if abs(drag_start_x - last_x) < SWIPE_THRESHOLD:
            # Calculate grid position
            start_x = (LEFT_PANEL_WIDTH - (GRID_COLS * ICON_SIZE + (GRID_COLS - 1) * ICON_SPACING)) // 2
            start_y = (SCREEN_HEIGHT - (GRID_ROWS * ICON_SIZE + (GRID_ROWS - 1) * ICON_SPACING) - 20) // 2
            
            # Validate coordinates before calculating tap position
            if (0 <= last_x < LEFT_PANEL_WIDTH and 
                0 <= last_y < SCREEN_HEIGHT and 
                start_x <= drag_start_x < start_x + GRID_COLS * (ICON_SIZE + ICON_SPACING)):
                
                # Calculate which icon was tapped
                col = (drag_start_x - start_x) // (ICON_SIZE + ICON_SPACING)
                row = (last_y - start_y) // (ICON_SIZE + ICON_SPACING)
                
                if 0 <= col < GRID_COLS and 0 <= row < GRID_ROWS:
                    items_per_page = GRID_COLS * GRID_ROWS
                    tapped_index = current_page * items_per_page + row * GRID_COLS + col
                    if 0 <= tapped_index < len(apps):
                        selected_app = tapped_index
                        draw_app_list(selected_app)
                        draw_right_panel(apps[selected_app])

# Initialize rotary encoder
encoder = RotaryEncoder(ROT_CLK, ROT_DT, ROT_SW)
display_on = True

# Initial draw
print("Drawing initial UI...")
selected_app = 0
draw_app_list(selected_app)
draw_right_panel(apps[selected_app])
print("Initial UI drawn")

# Main loop
print("Starting main loop...")
while True:
    # Handle touch input
    handle_touch()
    
    # Handle rotary encoder
    value_changed, button_pressed = encoder.read()
    
    # Handle button press
    if button_pressed:
        display_on = not display_on
        if display_on:
            led_pwm.duty_u16(encoder.get_value())
        else:
            led_pwm.duty_u16(0)
    
    # Handle rotation
    if value_changed and display_on:
        brightness = encoder.get_value()
        led_pwm.duty_u16(brightness)
        print(f"Brightness: {brightness}")
    
    time.sleep_ms(1)  # Small delay to prevent busy waiting 
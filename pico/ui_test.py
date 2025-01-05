from machine import Pin, SPI, I2C, PWM
from ili9488 import ILI9488
from ft6236 import FT6236
from rotary import RotaryEncoder
import time

# Constants and color definitions
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320
LEFT_PANEL_WIDTH = 160  # Width of app list panel
RIGHT_PANEL_WIDTH = SCREEN_WIDTH - LEFT_PANEL_WIDTH

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

# Scrolling and UI state variables
current_page = 0    # Current page number
is_dragging = False
drag_start_x = 0
SWIPE_THRESHOLD = 50  # Minimum pixels to trigger page change
selected_app = 0
last_x = 0
last_y = 0

# Display state variables
display_on = True
current_brightness = 65535  # Max brightness (16-bit PWM)

def set_display_brightness(brightness):
    """Set display brightness via PWM"""
    global current_brightness
    current_brightness = max(0, min(65535, brightness))  # Clamp between 0 and 65535
    if display_on:
        led_pwm.duty_u16(current_brightness)

def toggle_display():
    """Toggle display on/off"""
    global display_on
    display_on = not display_on
    led_pwm.duty_u16(current_brightness if display_on else 0)

# Function definitions
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
    
    # Draw media controls
    draw_media_controls()

def draw_media_controls(highlight_button=None):
    """Draw media control buttons (Play/Pause, Next, Previous) in their own section"""
    info_panel_width = RIGHT_PANEL_WIDTH - 100  # Main info area width
    media_section_height = 50  # Height of media control section
    button_height = 40
    
    # Draw dividing line above media controls
    y_divider = SCREEN_HEIGHT - media_section_height
    display.draw_hline(LEFT_PANEL_WIDTH, y_divider, info_panel_width, WHITE)
    
    # Calculate button dimensions and positions
    button_width = info_panel_width // 3  # Equal width for all three buttons
    button_y = y_divider + (media_section_height - button_height) // 2  # Center buttons vertically
    
    # Calculate x positions for buttons
    prev_x = LEFT_PANEL_WIDTH
    play_x = LEFT_PANEL_WIDTH + button_width
    next_x = LEFT_PANEL_WIDTH + 2 * button_width
    
    # Draw Previous button
    if highlight_button == 'prev':
        display.fill_rect(prev_x, button_y, button_width, button_height, GRAY)
        display.draw_text(prev_x + (button_width - 30) // 2, button_y + (button_height - 8) // 2, "Prev", BLACK, None)
    else:
        display.fill_rect(prev_x, button_y, button_width, button_height, DARK_GRAY)
        display.draw_text(prev_x + (button_width - 30) // 2, button_y + (button_height - 8) // 2, "Prev", WHITE, None)
    
    # Draw Play/Pause button
    if highlight_button == 'play':
        display.fill_rect(play_x, button_y, button_width, button_height, GRAY)
        display.draw_text(play_x + (button_width - 36) // 2, button_y + (button_height - 8) // 2, "Play", BLACK, None)
    else:
        display.fill_rect(play_x, button_y, button_width, button_height, DARK_GRAY)
        display.draw_text(play_x + (button_width - 36) // 2, button_y + (button_height - 8) // 2, "Play", WHITE, None)
    
    # Draw Next button
    if highlight_button == 'next':
        display.fill_rect(next_x, button_y, button_width, button_height, GRAY)
        display.draw_text(next_x + (button_width - 30) // 2, button_y + (button_height - 8) // 2, "Next", BLACK, None)
    else:
        display.fill_rect(next_x, button_y, button_width, button_height, DARK_GRAY)
        display.draw_text(next_x + (button_width - 30) // 2, button_y + (button_height - 8) // 2, "Next", WHITE, None)

def draw_buttons(highlight_button=None):
    """Draw the Mute/Mic buttons. If highlight_button is 'mute' or 'mic', draw it highlighted"""
    button_panel_width = 100
    button_panel_x = SCREEN_WIDTH - button_panel_width
    button_width = button_panel_width - 10
    button_height = SCREEN_HEIGHT // 2 - 5
    button_x = button_panel_x + 5
    
    # Only clear the specific button being highlighted
    if highlight_button == 'mute':
        display.fill_rect(button_x, 5, button_width, button_height, GRAY)
        display.draw_text(button_x + (button_width - 24) // 2, 5 + (button_height - 8) // 2, "Mute", BLACK, None)
    elif highlight_button == 'mic':
        display.fill_rect(button_x, button_height + 10, button_width, button_height, GRAY)
        display.draw_text(button_x + (button_width - 18) // 2, button_height + 10 + (button_height - 8) // 2, "Mic", BLACK, None)
    else:
        # Draw both buttons in normal state
        display.fill_rect(button_x, 5, button_width, button_height, DARK_GRAY)
        display.draw_text(button_x + (button_width - 24) // 2, 5 + (button_height - 8) // 2, "Mute", WHITE, None)
        
        display.fill_rect(button_x, button_height + 10, button_width, button_height, DARK_GRAY)
        display.draw_text(button_x + (button_width - 18) // 2, button_height + 10 + (button_height - 8) // 2, "Mic", WHITE, None)

def handle_touch():
    global current_page, is_dragging, drag_start_x, selected_app, last_x, last_y
    
    touched, raw_x, raw_y = touch.read_touch()
    
    if touched:
        x = max(0, min(SCREEN_WIDTH, 480 - int(raw_y)))
        y = max(0, min(SCREEN_HEIGHT, int(raw_x)))
        
        if x < 0 or x >= SCREEN_WIDTH or y < 0 or y >= SCREEN_HEIGHT:
            return
            
        last_x = x
        last_y = y
        print(f"\nTouch detected at x: {x}, y: {y}")
        
        # Handle media control touches
        info_panel_width = RIGHT_PANEL_WIDTH - 100
        media_section_height = 50
        y_divider = SCREEN_HEIGHT - media_section_height
        
        if LEFT_PANEL_WIDTH < x < SCREEN_WIDTH - 100 and y > y_divider:  # In media control section
            button_width = info_panel_width // 3
            
            # Calculate which button was pressed based on x position
            button_x = x - LEFT_PANEL_WIDTH
            button_index = button_x // button_width
            
            if button_index == 0:
                print("PREVIOUS TRACK")
                draw_media_controls('prev')
                time.sleep_ms(50)
                draw_media_controls()
            elif button_index == 1:
                print("PLAY/PAUSE")
                draw_media_controls('play')
                time.sleep_ms(50)
                draw_media_controls()
            elif button_index == 2:
                print("NEXT TRACK")
                draw_media_controls('next')
                time.sleep_ms(50)
                draw_media_controls()

        # Handle right panel touches (buttons)
        if x >= SCREEN_WIDTH - 100:  # Button panel width is 100
            button_height = SCREEN_HEIGHT // 2 - 5
            
            # Mute button (top half)
            if 5 <= y <= button_height:
                print("MUTE BUTTON PRESSED")
                draw_buttons('mute')  # Highlight mute button
                time.sleep_ms(50)  # Reduced delay
                draw_buttons()  # Return to normal
            # Mic button (bottom half)
            elif button_height + 10 <= y <= SCREEN_HEIGHT - 5:
                print("MIC BUTTON PRESSED")
                draw_buttons('mic')  # Highlight mic button
                time.sleep_ms(50)  # Reduced delay
                draw_buttons()  # Return to normal
        
        # Handle left panel touches (icon grid)
        elif x < LEFT_PANEL_WIDTH:
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

# Initialize hardware
print("Initializing display and touch...")

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
led_pwm.duty_u16(65535)  # Start at max brightness

# Initialize display pins
sck = Pin(SPI_SCK, Pin.OUT)
mosi = Pin(SPI_MOSI, Pin.OUT)
miso = Pin(SPI_MISO, Pin.IN)
dc = Pin(DC_PIN, Pin.OUT)
rst = Pin(RST_PIN, Pin.OUT)
cs = Pin(CS_PIN, Pin.OUT)

# Initialize SPI
spi = SPI(0,
          baudrate=62500000,   # 62.5MHz for faster drawing
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

# Initialize rotary encoder
print("Initializing rotary encoder...")
ROT_CLK = 14
ROT_DT = 15
ROT_SW = 13

encoder = RotaryEncoder(
    clk_pin=ROT_CLK,
    dt_pin=ROT_DT,
    sw_pin=ROT_SW,
    min_val=0,
    max_val=65535,
    step=4096,
    value=65535,
    debug=False  # Set to True to debug encoder issues
)

print("Starting UI test...")

# Clear screen
print("Clearing screen...")
display.fill(BLACK)

# Draw panel divider
print("Drawing panel divider...")
display.draw_vline(LEFT_PANEL_WIDTH, 0, SCREEN_HEIGHT, WHITE)

# Draw initial UI elements
print("Drawing initial UI...")
draw_app_list(0)  # Draw initial app list
draw_right_panel(apps[0])  # Draw initial app info
draw_buttons()  # Draw initial buttons

# Main loop
while True:
    # Handle touch events
    handle_touch()
    
    # Handle rotary encoder
    value_changed, button_pressed = encoder.read()
    
    if value_changed:
        # Update PWM directly with encoder value
        led_pwm.duty_u16(encoder.get_value())
        print(f"Brightness: {encoder.get_value()}")
    
    if button_pressed:
        # Toggle display on/off
        if led_pwm.duty_u16() > 0:
            led_pwm.duty_u16(0)  # Turn off
        else:
            led_pwm.duty_u16(encoder.get_value())  # Restore previous brightness
        print(f"Display {'Off' if led_pwm.duty_u16() == 0 else 'On'}")
    
    time.sleep_ms(10)  # Small delay to prevent overwhelming the processor
from machine import Pin, SPI, I2C, PWM
from ili9488 import ILI9488
from ft6236 import FT6236
import time

# Constants and color definitions
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320

# Colors (RGB565 format)
BLACK = 0x0000
WHITE = 0xFFFF
GRAY = 0x7BEF
DARK_GRAY = 0x39E7

# Button dimensions
SIDE_WIDTH = 100  # Width for prev/next buttons
CENTER_WIDTH = SCREEN_WIDTH - (2 * SIDE_WIDTH)  # Width for center section
CENTER_HEIGHT = SCREEN_HEIGHT // 2  # Height for mute/play buttons

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
spi = SPI(0,
          baudrate=62500000,   # 62.5MHz for faster drawing
          polarity=0,
          phase=0,
          bits=8,
          firstbit=SPI.MSB,
          sck=Pin(SPI_SCK),
          mosi=Pin(SPI_MOSI),
          miso=Pin(SPI_MISO))

display = ILI9488(spi, dc=Pin(DC_PIN, Pin.OUT), cs=Pin(CS_PIN, Pin.OUT), rst=Pin(RST_PIN, Pin.OUT))

# Touch controller initialization
TOUCH_SDA = 4
TOUCH_SCL = 5
TOUCH_INT = 6
TOUCH_RST = 7

rst_pin = Pin(TOUCH_RST, Pin.OUT)
rst_pin.value(0)
time.sleep_ms(10)
rst_pin.value(1)
time.sleep_ms(300)

i2c = I2C(0, sda=Pin(TOUCH_SDA), scl=Pin(TOUCH_SCL), freq=100000)
touch = FT6236(i2c, TOUCH_SDA, TOUCH_SCL)

def draw_button(button_id, x, y, width, height, text, highlighted=False):
    """Draw a single button with border"""
    # Draw button background
    color = GRAY if highlighted else DARK_GRAY
    display.fill_rect(x, y, width, height, color)
    
    # Draw border
    display.draw_rectangle(x, y, width, height, WHITE)
    
    # Center text
    text_width = len(text) * 16  # Assuming 16 pixels per character with scale=2
    text_x = x + (width - text_width) // 2
    text_y = y + (height - 16) // 2  # Assuming 16 pixels character height with scale=2
    
    # Draw text
    text_color = BLACK if highlighted else WHITE
    display.draw_text(text_x, text_y, text, text_color, None, scale=2)

def draw_initial_ui():
    """Draw the initial UI"""
    display.fill(BLACK)
    
    # Draw Previous button
    draw_button('prev', 0, 0, SIDE_WIDTH, SCREEN_HEIGHT, "PREV")
    
    # Draw Mute button (top center)
    draw_button('mute', SIDE_WIDTH, 0, CENTER_WIDTH, CENTER_HEIGHT, "MUTE")
    
    # Draw Play button (bottom center)
    draw_button('play', SIDE_WIDTH, CENTER_HEIGHT, CENTER_WIDTH, CENTER_HEIGHT, "PLAY")
    
    # Draw Next button
    draw_button('next', SCREEN_WIDTH - SIDE_WIDTH, 0, SIDE_WIDTH, SCREEN_HEIGHT, "NEXT")

def handle_touch():
    """Handle touch events and return the button pressed"""
    touched, raw_x, raw_y = touch.read_touch()
    
    if touched:
        # Convert touch coordinates
        x = max(0, min(SCREEN_WIDTH, 480 - int(raw_y)))
        y = max(0, min(SCREEN_HEIGHT, int(raw_x)))
        
        # Determine which button was pressed
        if x < SIDE_WIDTH:  # Previous button
            print("PREVIOUS pressed")
            draw_button('prev', 0, 0, SIDE_WIDTH, SCREEN_HEIGHT, "PREV", True)
            time.sleep_ms(100)
            draw_button('prev', 0, 0, SIDE_WIDTH, SCREEN_HEIGHT, "PREV", False)
            return 'prev'
            
        elif x >= SCREEN_WIDTH - SIDE_WIDTH:  # Next button
            print("NEXT pressed")
            draw_button('next', SCREEN_WIDTH - SIDE_WIDTH, 0, SIDE_WIDTH, SCREEN_HEIGHT, "NEXT", True)
            time.sleep_ms(100)
            draw_button('next', SCREEN_WIDTH - SIDE_WIDTH, 0, SIDE_WIDTH, SCREEN_HEIGHT, "NEXT", False)
            return 'next'
            
        elif SIDE_WIDTH <= x < SCREEN_WIDTH - SIDE_WIDTH:  # Center section
            if y < CENTER_HEIGHT:  # Mute button
                print("MUTE pressed")
                draw_button('mute', SIDE_WIDTH, 0, CENTER_WIDTH, CENTER_HEIGHT, "MUTE", True)
                time.sleep_ms(100)
                draw_button('mute', SIDE_WIDTH, 0, CENTER_WIDTH, CENTER_HEIGHT, "MUTE", False)
                return 'mute'
            else:  # Play button
                print("PLAY/PAUSE pressed")
                draw_button('play', SIDE_WIDTH, CENTER_HEIGHT, CENTER_WIDTH, CENTER_HEIGHT, "PLAY", True)
                time.sleep_ms(100)
                draw_button('play', SIDE_WIDTH, CENTER_HEIGHT, CENTER_WIDTH, CENTER_HEIGHT, "PLAY", False)
                return 'play'
    
    return None

# Draw initial UI
print("Drawing initial UI...")
draw_initial_ui()

# Main loop
while True:
    handle_touch()
    time.sleep_ms(10) 
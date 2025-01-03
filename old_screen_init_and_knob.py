from machine import Pin, SPI, PWM
import time
from rotary import RotaryEncoder

print("Starting display test...")

# Display Pins
SPI_SCK = 18    # Pin 7 on LCD
SPI_MOSI = 19   # Pin 6 on LCD
SPI_MISO = 16   # Pin 9 on LCD
DC_PIN = 20     # Pin 5 on LCD
RST_PIN = 21    # Pin 4 on LCD
CS_PIN = 17     # Pin 3 on LCD
LED_PIN = 22    # Pin 8 on LCD

# Rotary Encoder Pins
ROT_CLK = 14
ROT_DT = 15
ROT_SW = 13

# Initialize display pins
sck = Pin(SPI_SCK, Pin.OUT)
mosi = Pin(SPI_MOSI, Pin.OUT)
miso = Pin(SPI_MISO, Pin.IN)
dc = Pin(DC_PIN, Pin.OUT)
rst = Pin(RST_PIN, Pin.OUT)
cs = Pin(CS_PIN, Pin.OUT)

# Initialize LED backlight with PWM
led_pwm = PWM(Pin(LED_PIN))
led_pwm.freq(1000)  # Set PWM frequency to 1kHz
brightness = 65535  # Max brightness (16-bit PWM)
led_pwm.duty_u16(brightness)

# Initialize rotary encoder
encoder = RotaryEncoder(ROT_CLK, ROT_DT, ROT_SW)
display_on = True

# Display command functions
def write_cmd(cmd):
    cs.value(0)
    dc.value(0)  # Command mode
    spi.write(bytearray([cmd]))
    cs.value(1)
    time.sleep_ms(1)

def write_data(data):
    cs.value(0)
    dc.value(1)  # Data mode
    spi.write(data)
    cs.value(1)
    time.sleep_ms(1)

def fill_rect(x, y, w, h, color):
    # Set column address
    write_cmd(0x2A)
    write_data(bytearray([x >> 8, x & 0xFF, (x + w - 1) >> 8, (x + w - 1) & 0xFF]))
    
    # Set row address
    write_cmd(0x2B)
    write_data(bytearray([y >> 8, y & 0xFF, (y + h - 1) >> 8, (y + h - 1) & 0xFF]))
    
    # Write to RAM
    write_cmd(0x2C)
    cs.value(0)
    dc.value(1)
    
    # Create buffer for one row
    pixels_per_write = min(w, 160)  # Limit buffer size
    buffer = bytearray(color * pixels_per_write)
    
    # Fill rectangle
    for _ in range(h):
        for x_pos in range(0, w, pixels_per_write):
            pixels = min(pixels_per_write, w - x_pos)
            spi.write(buffer[:pixels * 3])  # 3 bytes per pixel
    
    cs.value(1)

# Initialize SPI
spi = SPI(0,
          baudrate=1000000,   # 1MHz
          polarity=0,
          phase=0,
          bits=8,
          firstbit=SPI.MSB,
          sck=Pin(SPI_SCK),
          mosi=Pin(SPI_MOSI),
          miso=Pin(SPI_MISO))

# Hardware reset
print("Resetting display...")
rst.value(0)
time.sleep_ms(100)
rst.value(1)
time.sleep_ms(100)

# Basic initialization
print("Initializing display...")

write_cmd(0x01)    # Software reset
time.sleep_ms(100)

write_cmd(0x11)    # Sleep out
time.sleep_ms(100)

write_cmd(0xE0)    # Positive Gamma Control
write_data(bytearray([0x00, 0x03, 0x09, 0x08, 0x16, 0x0A, 0x3F, 0x78,
                     0x4C, 0x09, 0x0A, 0x08, 0x16, 0x1A, 0x0F]))

write_cmd(0xE1)    # Negative Gamma Control
write_data(bytearray([0x00, 0x16, 0x19, 0x03, 0x0F, 0x05, 0x32, 0x45,
                     0x46, 0x04, 0x0E, 0x0D, 0x35, 0x37, 0x0F]))

write_cmd(0xC0)    # Power Control 1
write_data(bytearray([0x17, 0x15]))

write_cmd(0xC1)    # Power Control 2
write_data(bytearray([0x41]))

write_cmd(0xC5)    # VCOM Control
write_data(bytearray([0x00, 0x12, 0x80]))

write_cmd(0x36)    # Memory Access Control
write_data(bytearray([0xE8]))  # MY, MX, BGR mode

write_cmd(0x3A)    # Interface Pixel Format
write_data(bytearray([0x66]))  # 18-bit color format

write_cmd(0xB1)    # Frame Rate Control
write_data(bytearray([0x00, 0x18]))

write_cmd(0xB6)    # Display Function Control
write_data(bytearray([0x02, 0x02]))

write_cmd(0xF6)    # Interface Control
write_data(bytearray([0x01, 0x30, 0x00]))

write_cmd(0xF2)    # Enable 3G
write_data(bytearray([0x00]))

write_cmd(0x26)    # Gamma Set
write_data(bytearray([0x01]))

write_cmd(0x29)    # Display ON
time.sleep_ms(100)

# Draw test pattern
print("Drawing test pattern...")

# Define colors (RGB format)
RED = [0xFF, 0x00, 0x00]
GREEN = [0x00, 0xFF, 0x00]
BLUE = [0x00, 0x00, 0xFF]
WHITE = [0xFF, 0xFF, 0xFF]
BLACK = [0x00, 0x00, 0x00]
YELLOW = [0xFF, 0xFF, 0x00]
CYAN = [0x00, 0xFF, 0xFF]
MAGENTA = [0xFF, 0x00, 0xFF]

# Clear screen to black
fill_rect(0, 0, 480, 320, BLACK)

# Draw color bars
colors = [RED, GREEN, BLUE, WHITE, YELLOW, CYAN, MAGENTA]
bar_width = 480 // len(colors)
for i, color in enumerate(colors):
    fill_rect(i * bar_width, 0, bar_width, 320 // 2, color)

# Draw checkerboard pattern in bottom half
square_size = 40
for y in range(320 // 2, 320, square_size):
    for x in range(0, 480, square_size):
        if (x + y) // square_size % 2:
            fill_rect(x, y, square_size, square_size, WHITE)
        else:
            fill_rect(x, y, square_size, square_size, BLACK)

print("Test pattern complete")

# Main loop
print("Starting main loop...")
while True:
    # Read encoder
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
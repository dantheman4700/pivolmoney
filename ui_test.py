from machine import Pin, SPI
from ili9488 import ILI9488
import time

print("Initializing display...")

# Display Pins
SPI_SCK = 18    # Pin 7 on LCD
SPI_MOSI = 19   # Pin 6 on LCD
SPI_MISO = 16   # Pin 9 on LCD
DC_PIN = 20     # Pin 5 on LCD
RST_PIN = 21    # Pin 4 on LCD
CS_PIN = 17     # Pin 3 on LCD

# Initialize display pins
sck = Pin(SPI_SCK, Pin.OUT)
mosi = Pin(SPI_MOSI, Pin.OUT)
miso = Pin(SPI_MISO, Pin.IN)
dc = Pin(DC_PIN, Pin.OUT)
rst = Pin(RST_PIN, Pin.OUT)
cs = Pin(CS_PIN, Pin.OUT)

# Complete reset sequence
print("Performing complete reset sequence...")
cs.value(1)  # CS high
dc.value(0)  # DC low
rst.value(1)  # RST high
time.sleep_ms(50)
rst.value(0)  # RST low
time.sleep_ms(150)
rst.value(1)  # RST high
time.sleep_ms(150)

# Initialize SPI exactly as in main.py
spi = SPI(0,
          baudrate=62500000,   # Increase to 62.5MHz for fastest possible fills
          polarity=0,
          phase=0,
          bits=8,
          firstbit=SPI.MSB,
          sck=Pin(SPI_SCK),
          mosi=Pin(SPI_MOSI),
          miso=Pin(SPI_MISO))

display = ILI9488(spi, dc=dc, cs=cs, rst=rst)

# Define some colors (RGB565 format)
BLACK = 0x0000
WHITE = 0xFFFF
RED = 0xF800
GREEN = 0x07E0
BLUE = 0x001F

print("Starting display test...")

# Clear to black first and wait for it to complete
print("Filling screen with black")
display.fill(BLACK)
time.sleep_ms(100)  # Wait for fill to complete

# Now create a simpler test pattern that's more readable
display.fill(BLACK)
time.sleep_ms(50)

# Draw a border
display.draw_rectangle(5, 5, 470, 310, WHITE, filled=False)

# Title with large scale
display.draw_text(20, 20, "Volume Control", WHITE, scale=3)

# Draw some example volume bars
apps = ["Chrome", "Spotify", "Discord", "Game"]
y = 80
for i, app in enumerate(apps):
    # Draw app name
    display.draw_text(20, y, app, WHITE, scale=2)
    # Draw volume bar
    display.draw_progress_bar(150, y, 300, 25, (i+1)*25, GREEN, BLACK, WHITE)
    y += 50

# Draw status at bottom
display.draw_text(20, 280, "Touch to select - Rotate to adjust", WHITE, scale=2)

while True:
    time.sleep(1)  # Keep the display on 
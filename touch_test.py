from machine import Pin, I2C
import time
from ft6236 import FT6236

# Touch controller pins
TOUCH_SDA = 4   # GP4
TOUCH_SCL = 5   # GP5
TOUCH_INT = 6   # GP6
TOUCH_RST = 7   # GP7

print("Initializing touch controller...")

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

# Scan for I2C devices
devices = i2c.scan()
print(f"I2C devices found: {[hex(d) for d in devices]}")

# Initialize touch controller
try:
    touch = FT6236(i2c, TOUCH_SDA, TOUCH_SCL)
    print("Touch controller initialized successfully")
    
    print("\nStarting touch test. Touch the screen to see coordinates.")
    print("Press Ctrl+C to exit.")
    
    last_x = 0
    last_y = 0
    
    while True:
        touched, x, y = touch.read_touch()
        
        # Only print if coordinates changed significantly (to reduce noise)
        if touched and (abs(x - last_x) > 5 or abs(y - last_y) > 5):
            print(f"Touch detected at X: {x}, Y: {y}")
            last_x = x
            last_y = y
            
            # Print raw register values for debugging
            try:
                status = touch._read_reg(0x02)[0]  # TD_STATUS
                x_h = touch._read_reg(0x03)[0]     # P1_XH
                x_l = touch._read_reg(0x04)[0]     # P1_XL
                y_h = touch._read_reg(0x05)[0]     # P1_YH
                y_l = touch._read_reg(0x06)[0]     # P1_YL
                print(f"Raw values - Status: {hex(status)}, X: {hex(x_h)}{hex(x_l)}, Y: {hex(y_h)}{hex(y_l)}")
            except Exception as e:
                print(f"Error reading raw values: {e}")
        
        time.sleep_ms(20)  # Poll faster
        
except Exception as e:
    print(f"Failed to initialize touch controller: {e}")
    raise
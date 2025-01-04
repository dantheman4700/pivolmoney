import time
from HID_new import CustomHIDDevice

print("This script will switch the Pico to Custom HID mode.")
print("Thonny will disconnect when this happens.")
print("The device will echo back any data it receives.")
print()
print("Starting in 3 seconds...")
time.sleep(3)

# Create device
device = CustomHIDDevice()

print("Switching to HID mode...")
if not device.init():
    print("Failed to initialize device!")
    raise SystemExit

print("Device initialized, sending test sequence...")

# Send a sequence of test patterns
test_patterns = [
    bytes([0x01, 0x02, 0x03, 0x04]),  # Simple sequence
    bytes([0xFF, 0x00, 0xFF, 0x00]),  # Alternating pattern
    bytes([0x55, 0xAA, 0x55, 0xAA])   # Another pattern
]

for i, pattern in enumerate(test_patterns, 1):
    print(f"\nSending test pattern {i}: {[hex(x) for x in pattern]}")
    device.send_data(pattern)
    time.sleep(1)  # Wait between patterns

print("\nTest patterns sent. Now waiting for any incoming data.")
print("The device will echo back any data it receives.")
print("Press Ctrl+C to exit...")

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nExiting...")

# Switch back to CDC mode
print("Switching back to CDC mode...")
device.deinit()

print("Test complete! You can reconnect in Thonny now.") 
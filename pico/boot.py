# boot.py -- run on boot-up
import machine
import os

# Try to mount the filesystem
try:
    os.mount(machine.Flash(), "/")
except:
    print("Filesystem already mounted")

# Configure CPU frequency
machine.freq(125_000_000)  # Set CPU frequency

# Create a flag file to indicate successful boot
with open("boot_complete.txt", "w") as f:
    f.write("Boot completed") 
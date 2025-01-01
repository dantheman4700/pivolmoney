# boot.py -- run on boot-up
import machine
import os

# Try to mount the filesystem
try:
    os.mount(machine.Flash(), "/")
except:
    print("Filesystem already mounted")

# Create a flag file to indicate successful boot
with open("boot_complete.txt", "w") as f:
    f.write("Boot completed") 
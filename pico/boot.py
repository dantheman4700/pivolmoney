# boot.py -- run on boot-up
import machine
import os

# Try to mount the filesystem
try:
    os.mount(machine.Flash(), "/")
except:
    print("Filesystem already mounted") 
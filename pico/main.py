from app_volume_serial import AppVolumeController
import time

def main():
    controller = AppVolumeController()
    
    while True:
        controller.update()
        time.sleep(0.01)

if __name__ == "__main__":
    main() 
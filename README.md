# Raspberry Pi Pico Volume Control Panel

A USB HID device for controlling system-wide media playback and application-specific volume levels using a Raspberry Pi Pico. Features a touchscreen display for visual feedback and control. The device functions as both a media control HID device and communicates with a PC application for granular volume control.

## Features

- System-wide media controls (HID):
  - Volume Up/Down
  - Mute
  - Play/Pause
  - Next/Previous Track
- Application-specific volume control
- Plug-and-play USB device
- Real-time application volume monitoring
- Interactive touchscreen interface:
  - ILI9488 Display Driver
  - FT6236 Touch Controller
  - Custom UI elements and icons
  - Visual volume feedback

## Hardware Requirements

- Raspberry Pi Pico
- ILI9488-based LCD Display
- FT6236 Touch Controller
- Rotary Encoder (optional)

## Project Structure

```
.
├── pc/                     # PC-side code
│   └── windows_volume_control.py  # Windows volume control application
├── pico/                   # Pico-side code
│   ├── main.py            # Main Pico application
│   ├── boot.py            # Pico boot configuration
│   ├── volume_control_hid.py    # HID implementation
│   ├── app_volume_serial.py     # Serial communication
│   ├── ili9488.py         # Display driver
│   ├── ft6236.py          # Touch controller driver
│   ├── icons.py           # UI icons and graphics
│   ├── font8x8.py         # Font definitions
│   └── rotary.py          # Rotary encoder handler
└── reference_code/         # Example and reference code
```

## Setup

### Hardware Setup
1. Connect the ILI9488 display to the Pico:
   - SPI interface for display
   - I2C for touch controller
2. (Optional) Connect rotary encoder
3. Detailed pinout configuration in `boot.py`

### PC Requirements
1. Python 3.7+
2. Required packages:
```bash
pip install pyserial
pip install pycaw
```

### Pico Setup
1. Flash the Pico with MicroPython
2. Copy all files from the `pico/` directory to the Pico

## Usage

1. Connect the Pico to your PC via USB
2. Run the Windows application:
```bash
python pc/windows_volume_control.py
```
3. The Pico will automatically be recognized as:
   - HID Media Control device
   - Serial device for app-specific control
4. Use the touchscreen to:
   - Adjust system volume
   - Control media playback
   - View and control application volumes
   - Navigate through the UI

## Development

- `/pc`: Contains the Windows application for handling application-specific volume control
- `/pico`: Contains the MicroPython code for the Pico
  - UI and display drivers
  - Touch input handling
  - HID and serial communication
- `/reference_code`: Contains example code and references (not used in production)

## License

MIT License 
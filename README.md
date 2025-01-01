# ILI9488 Display Driver for Raspberry Pi Pico

A MicroPython driver for the ILI9488 display controller with rotary encoder control, specifically designed for use with the Raspberry Pi Pico.

## Features

- SPI interface communication
- 18-bit color support
- Basic drawing functions (rectangles, screen filling)
- Color bar test patterns
- Hardware reset and initialization
- PWM backlight control
- Rotary encoder support for:
  - Brightness control (16 steps)
  - Display on/off toggle

## Hardware Requirements

- Raspberry Pi Pico
- ILI9488-based display (480x320 resolution)
- Rotary encoder with push button

### Display Connections
- SCK -> GP18
- MOSI -> GP19
- MISO -> GP16
- DC -> GP20
- RST -> GP21
- CS -> GP17
- LED -> GP22 (PWM controlled)

### Rotary Encoder Connections
- CLK -> GP14
- DT -> GP15
- SW -> GP13

## Files

- `main.py`: Main program with display initialization and control loop
- `rotary.py`: Rotary encoder driver with debouncing
- `ili9488.py`: Display driver implementation
- `font8x8.py`: Basic 8x8 font for text display

## Usage

1. Connect the display and rotary encoder to the Raspberry Pi Pico according to the pin mappings above
2. Copy all the Python files to the Pico
3. Reset the Pico to run the program
4. Use the rotary encoder to control the display:
   - Turn clockwise to increase brightness
   - Turn counter-clockwise to decrease brightness
   - Press the button to toggle display on/off

## Current Status

Basic driver implementation with:
- Display initialization
- Color configuration
- Rectangle drawing
- Test patterns
- Brightness control
- Display power management

## Future Improvements

- Additional drawing functions (lines, circles, triangles)
- Text rendering
- Image display
- Display rotation
- Hardware acceleration
- Scrolling support
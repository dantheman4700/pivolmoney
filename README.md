# ILI9488 Display Driver for Raspberry Pi Pico

A MicroPython driver for the ILI9488 display controller, specifically designed for use with the Raspberry Pi Pico.

## Features

- SPI interface communication
- 18-bit color support
- Basic drawing functions (rectangles, screen filling)
- Color bar test patterns
- Hardware reset and initialization

## Hardware Requirements

- Raspberry Pi Pico
- ILI9488-based display (480x320 resolution)
- Connections:
  - SCK -> GP18
  - MOSI -> GP19
  - MISO -> GP16
  - DC -> GP20
  - RST -> GP21
  - CS -> GP17
  - LED -> GP22

## Files

- `main.py`: Main program and test patterns
- `ili9488.py`: Display driver implementation
- `font8x8.py`: Basic 8x8 font for text display

## Usage

1. Connect the display to the Raspberry Pi Pico according to the pin mappings above
2. Copy all the Python files to the Pico
3. Reset the Pico to run the test pattern

## Current Status

Basic driver implementation with:
- Display initialization
- Color configuration
- Rectangle drawing
- Test patterns

## Future Improvements

- Additional drawing functions (lines, circles, triangles)
- Text rendering
- Image display
- Display rotation
- Hardware acceleration
- Scrolling support 
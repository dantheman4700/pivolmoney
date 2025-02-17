from machine import Pin
import time
from core.logger import get_logger
from core.config import (
    ENCODER_MIN_VAL, ENCODER_MAX_VAL, ENCODER_STEP,
    ENCODER_DEBOUNCE_MS, PIN_ROT_CLK, PIN_ROT_DT, PIN_ROT_SW
)

class RotaryEncoder:
    def __init__(self, clk_pin=None, dt_pin=None, sw_pin=None, min_val=ENCODER_MIN_VAL, 
                 max_val=ENCODER_MAX_VAL, step=ENCODER_STEP, value=0, debug=False):
        """Initialize Rotary Encoder with specified pins and range"""
        self.logger = get_logger()
        
        # Use default pins if none provided
        if clk_pin is None:
            clk_pin = PIN_ROT_CLK
        if dt_pin is None:
            dt_pin = PIN_ROT_DT
        if sw_pin is None:
            sw_pin = PIN_ROT_SW
            
        # Initialize pins with pull-ups for CLK and DT, but not SW
        self.clk = Pin(clk_pin, Pin.IN, Pin.PULL_UP)
        self.dt = Pin(dt_pin, Pin.IN, Pin.PULL_UP)
        self.sw = Pin(sw_pin, Pin.IN)  # No pull-up for SW as it's directly connected
        
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self._value = max(min_val, min(max_val, value))
        self.debug = debug
        
        # Initialize timing and state for simple edge detection
        current_time = time.ticks_ms()
        self.last_value_change = current_time  # For debouncing value changes
        self.last_button_time = current_time     # For debouncing the button press
        
        # NEW: Initialize last_clk for rising edge detection
        self.last_clk = self.clk.value()
        self.last_button = self.sw.value()
        
        self.logger.info(f"Rotary encoder initialized: CLK={clk_pin}, DT={dt_pin}, SW={sw_pin}")
        # Log the initial CLK reading as a binary string (2 digits)
        binary_str = bin(self.last_clk)[2:]
        if len(binary_str) < 2:
            binary_str = '0' + binary_str
        self.logger.info(f"Initial CLK state: {binary_str}")
        
    def read(self):
        """Simplified read method using rising edge detection on CLK.
        Returns (value_changed, button_pressed)."""
        value_changed = False
        button_pressed = False
        
        current_millis = time.ticks_ms()
        clk_val = self.clk.value()
        dt_val = self.dt.value()
        sw_val = self.sw.value()
        
        # Simple rising edge detection on CLK: from 0 to 1
        if self.last_clk == 0 and clk_val == 1:
            # Check if enough time has passed to debounce the event
            if time.ticks_diff(current_millis, self.last_value_change) > ENCODER_DEBOUNCE_MS:
                # Determine direction based on DT pin state
                if dt_val == 0:  # Typically means a clockwise turn
                    new_value = min(self._value + self.step, self.max_val)
                    if new_value != self._value:
                        self._value = new_value
                        value_changed = True
                        self.logger.info(f"Value increased to: {self._value}")
                else:           # Otherwise, treat as counter-clockwise
                    new_value = max(self._value - self.step, self.min_val)
                    if new_value != self._value:
                        self._value = new_value
                        value_changed = True
                        self.logger.info(f"Value decreased to: {self._value}")
                    
                self.last_value_change = current_millis
        
        # Update last_clk for next detection cycle
        self.last_clk = clk_val
        
        # Button debouncing (unchanged)
        if sw_val != self.last_button:
            button_time_diff = time.ticks_diff(current_millis, self.last_button_time)
            if button_time_diff > 50:
                if not sw_val:  # Button pressed (active low)
                    button_pressed = True
                    self.logger.info("Button pressed!")
                self.last_button_time = current_millis
            self.last_button = sw_val
        
        return value_changed, button_pressed
    
    def get_value(self):
        """Get current value"""
        return self._value
    
    def set_value(self, value):
        """Set current value within bounds"""
        self._value = max(self.min_val, min(self.max_val, value))
        return self._value 
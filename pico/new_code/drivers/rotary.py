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
        
        self.last_clk = self.clk.value()
        self.last_dt = self.dt.value()
        self.last_sw = self.sw.value()
        self.last_button_time = time.ticks_ms()
        self.button_debounce = ENCODER_DEBOUNCE_MS
        
        self.logger.info(f"Rotary encoder initialized: CLK={clk_pin}, DT={dt_pin}, SW={sw_pin}")
        
    def read(self):
        """Read encoder state and return (value_changed, button_pressed)"""
        value_changed = False
        button_pressed = False
        
        try:
            # Read current pin states
            clk_val = self.clk.value()
            dt_val = self.dt.value()
            sw_val = self.sw.value()
            
            # Check for rotation
            if clk_val != self.last_clk:
                if dt_val != clk_val:  # Clockwise
                    new_value = self._value + self.step
                    if new_value <= self.max_val:
                        self._value = new_value
                        value_changed = True
                        if self.debug:
                            self.logger.debug(f"Rotary CW: {self._value}")
                else:  # Counter-clockwise
                    new_value = self._value - self.step
                    if new_value >= self.min_val:
                        self._value = new_value
                        value_changed = True
                        if self.debug:
                            self.logger.debug(f"Rotary CCW: {self._value}")
            
            # Check for button press with debounce
            current_time = time.ticks_ms()
            if sw_val != self.last_sw and time.ticks_diff(current_time, self.last_button_time) > self.button_debounce:
                if sw_val == 0:  # Button pressed (active low)
                    button_pressed = True
                    if self.debug:
                        self.logger.debug("Button pressed")
                self.last_button_time = current_time
            
            # Update last states
            self.last_clk = clk_val
            self.last_dt = dt_val
            self.last_sw = sw_val
            
        except Exception as e:
            self.logger.error(f"Error reading rotary encoder: {str(e)}")
        
        return value_changed, button_pressed
    
    def get_value(self):
        """Get current value"""
        return self._value
    
    def set_value(self, value):
        """Set current value within bounds"""
        self._value = max(self.min_val, min(self.max_val, value))
        return self._value 
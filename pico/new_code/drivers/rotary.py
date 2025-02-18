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
            
        # Initialize pins with pull-ups for all pins
        self.clk = Pin(clk_pin, Pin.IN, Pin.PULL_UP)
        self.dt = Pin(dt_pin, Pin.IN, Pin.PULL_UP)
        self.sw = Pin(sw_pin, Pin.IN, Pin.PULL_UP)  # Added pull-up for SW
        
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self._value = max(min_val, min(max_val, value))
        self.debug = debug
        
        # Initialize timing and state variables
        self.last_interrupt_time = time.ticks_ms()
        self.last_button_time = self.last_interrupt_time
        
        # Initialize state tracking
        self.last_state = self._read_state()
        self.last_button = self.sw.value()
        
        # Set up interrupts for better response
        self.clk.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self._handle_rotation)
        self.dt.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self._handle_rotation)
        self.sw.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self._handle_button)
        
        self.logger.info(f"Rotary encoder initialized: CLK={clk_pin}, DT={dt_pin}, SW={sw_pin}")
        # Convert state to binary string in MicroPython compatible way
        binary_str = '0' * (2 - len(bin(self.last_state)[2:])) + bin(self.last_state)[2:]
        self.logger.info(f"Initial state: {binary_str}")
    
    def _read_state(self):
        """Read current encoder state"""
        return (self.clk.value() << 1) | self.dt.value()
    
    def _handle_rotation(self, pin):
        """Interrupt handler for rotation"""
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_interrupt_time) > 1:  # 1ms debounce
            new_state = self._read_state()
            
            if new_state != self.last_state:
                if self.debug:
                    self.logger.debug(f"Rotation interrupt - CLK: {self.clk.value()}, DT: {self.dt.value()}")
                
                # Detect direction based on state transition
                if (self.last_state == 0b00 and new_state == 0b01) or \
                   (self.last_state == 0b01 and new_state == 0b11) or \
                   (self.last_state == 0b11 and new_state == 0b10) or \
                   (self.last_state == 0b10 and new_state == 0b00):
                    self._value = min(self._value + self.step, self.max_val)
                    if self.debug:
                        self.logger.debug("Clockwise rotation")
                
                elif (self.last_state == 0b00 and new_state == 0b10) or \
                     (self.last_state == 0b10 and new_state == 0b11) or \
                     (self.last_state == 0b11 and new_state == 0b01) or \
                     (self.last_state == 0b01 and new_state == 0b00):
                    self._value = max(self._value - self.step, self.min_val)
                    if self.debug:
                        self.logger.debug("Counter-clockwise rotation")
                
                self.last_state = new_state
            self.last_interrupt_time = current_time
    
    def _handle_button(self, pin):
        """Interrupt handler for button press"""
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_button_time) > 50:  # 50ms debounce
            button_val = self.sw.value()
            if button_val != self.last_button:
                self.last_button = button_val
                if self.debug:
                    self.logger.debug(f"Button state changed: {button_val}")
            self.last_button_time = current_time
    
    def read(self):
        """Read encoder state and return if value changed and button state"""
        try:
            # Get current button state (active low)
            button_pressed = not self.sw.value()
            
            # Check if value has changed since last read
            current_value = self._value
            value_changed = current_value != self._last_value if hasattr(self, '_last_value') else True
            self._last_value = current_value
            
            return value_changed, button_pressed
            
        except Exception as e:
            self.logger.error(f"Error reading encoder: {str(e)}")
            return False, False
    
    def get_value(self):
        """Get current value"""
        return self._value
    
    def set_value(self, value):
        """Set current value within bounds"""
        self._value = max(self.min_val, min(self.max_val, value))
        return self._value 
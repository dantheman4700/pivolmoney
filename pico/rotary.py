from machine import Pin
import time

class RotaryEncoder:
    def __init__(self, clk_pin, dt_pin, sw_pin, min_val=0, max_val=65535, step=4096, value=65535, debug=False):
        # Initialize pins
        self.clk = Pin(clk_pin, Pin.IN, Pin.PULL_UP)
        self.dt = Pin(dt_pin, Pin.IN, Pin.PULL_UP)
        self.sw = Pin(sw_pin, Pin.IN, Pin.PULL_UP)
        
        # Initialize values
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.value = value
        self.debug = debug
        
        # Enhanced state tracking
        self.last_clk = self.clk.value()
        self.last_dt = self.dt.value()
        self.last_encoded = (self.last_clk << 1) | self.last_dt
        self.last_change = time.ticks_ms()
        self.button_pressed = False
        self.last_button_time = time.ticks_ms()
        self.last_direction = None  # Track last direction for consistency check
        
        # Set up button callback
        self.sw.irq(trigger=Pin.IRQ_FALLING, handler=self._button_callback)
        
    def _button_callback(self, pin):
        # Debounce button
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_button_time) > 200:  # 200ms debounce
            self.button_pressed = True
            self.last_button_time = current_time
    
    def read(self):
        """Read encoder value and button state. Returns (value_changed, button_pressed)"""
        value_changed = False
        button_pressed = False
        
        # Check if button was pressed
        if self.button_pressed:
            button_pressed = True
            self.button_pressed = False
        
        # Read current state
        clk_state = self.clk.value()
        dt_state = self.dt.value()
        
        # Get current time for debouncing
        current_time = time.ticks_ms()
        
        # Create a binary encoding of the rotation state
        encoded = (clk_state << 1) | dt_state
        
        # Check if state has changed and enough time has passed (debouncing)
        if encoded != self.last_encoded and time.ticks_diff(current_time, self.last_change) > 2:  # Increased debounce time
            if self.debug:
                print(f"State change: {bin(self.last_encoded)[2:]:>02} -> {bin(encoded)[2:]:>02}")
            
            # Determine direction based on state transition
            direction = None
            
            if (self.last_encoded == 0b00 and encoded == 0b10) or \
               (self.last_encoded == 0b10 and encoded == 0b11) or \
               (self.last_encoded == 0b11 and encoded == 0b01) or \
               (self.last_encoded == 0b01 and encoded == 0b00):
                direction = "CW"
                # Only change value if direction is consistent
                if self.last_direction in (None, "CW"):
                    if self.value + self.step <= self.max_val:
                        self.value += self.step
                        value_changed = True
                        if self.debug:
                            print(f"Clockwise: {self.value}")
            
            elif (self.last_encoded == 0b00 and encoded == 0b01) or \
                 (self.last_encoded == 0b01 and encoded == 0b11) or \
                 (self.last_encoded == 0b11 and encoded == 0b10) or \
                 (self.last_encoded == 0b10 and encoded == 0b00):
                direction = "CCW"
                # Only change value if direction is consistent
                if self.last_direction in (None, "CCW"):
                    if self.value - self.step >= self.min_val:
                        self.value -= self.step
                        value_changed = True
                        if self.debug:
                            print(f"Counter-clockwise: {self.value}")
            
            # Update state tracking
            self.last_encoded = encoded
            self.last_change = current_time
            self.last_direction = direction
            
            # Reset direction after a short delay
            if time.ticks_diff(current_time, self.last_change) > 50:
                self.last_direction = None
        
        return value_changed, button_pressed
    
    def get_value(self):
        """Get current value"""
        return self.value 
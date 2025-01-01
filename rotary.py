from machine import Pin
import time

class RotaryEncoder:
    def __init__(self, clk_pin, dt_pin, sw_pin, min_val=0, max_val=65535, step=4096, value=65535):
        # Initialize pins
        self.clk = Pin(clk_pin, Pin.IN, Pin.PULL_UP)
        self.dt = Pin(dt_pin, Pin.IN, Pin.PULL_UP)
        self.sw = Pin(sw_pin, Pin.IN, Pin.PULL_UP)
        
        # Initialize values
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.value = value
        self.last_clk = self.clk.value()
        self.button_pressed = False
        self.last_button_time = time.ticks_ms()
        
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
        
        # Read rotary encoder
        clk_state = self.clk.value()
        if clk_state != self.last_clk:
            if self.dt.value() != clk_state:  # Clockwise
                if self.value + self.step <= self.max_val:
                    self.value += self.step
                    value_changed = True
            else:  # Counter-clockwise
                if self.value - self.step >= self.min_val:
                    self.value -= self.step
                    value_changed = True
            self.last_clk = clk_state
        
        return value_changed, button_pressed
    
    def get_value(self):
        """Get current value"""
        return self.value 
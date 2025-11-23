from machine import Pin, Timer
import time
from micropython import const

# Pin definitions - actual hardware connections
PIN_ROT_CLK = const(20)  # GPIO20
PIN_ROT_DT = const(21)   # GPIO21
PIN_ROT_SW = const(22)   # GPIO22

def format_binary(num):
    """Convert number to 2-digit binary string"""
    return '0' * (2 - len(bin(num)[2:])) + bin(num)[2:]

class EncoderTester:
    def __init__(self, clk_pin=PIN_ROT_CLK, dt_pin=PIN_ROT_DT, sw_pin=PIN_ROT_SW):
        print(f"\nInitializing encoder with pins:")
        print(f"CLK: GPIO{clk_pin}")
        print(f"DT:  GPIO{dt_pin}")
        print(f"SW:  GPIO{sw_pin}")
        
        # Initialize pins with pull-ups and interrupts
        self.clk = Pin(clk_pin, Pin.IN, Pin.PULL_UP)
        self.dt = Pin(dt_pin, Pin.IN, Pin.PULL_UP)
        self.sw = Pin(sw_pin, Pin.IN, Pin.PULL_UP)
        
        # State tracking
        self.last_state = self._read_state()
        print(f"Initial state: {format_binary(self.last_state)}")
        self.value = 50
        self.min_val = 0
        self.max_val = 100
        self.last_interrupt_time = 0
        
        # Testing metrics
        self.metrics = {
            'total_rotations': 0,
            'cw_rotations': 0,
            'ccw_rotations': 0,
            'button_presses': 0,
            'bounce_events': 0,
            'state_changes': 0,
            'rotation_intervals': []
        }
        
        # Debug: Initial pin states
        print("\nInitial pin states:")
        print(f"CLK: {self.clk.value()}")
        print(f"DT:  {self.dt.value()}")
        print(f"SW:  {self.sw.value()}")
        
        # Set up interrupts with both edges for better detection
        self.clk.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self._handle_rotation)
        self.dt.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self._handle_rotation)  # Monitor both pins
        self.sw.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self._handle_button)  # Monitor both edges for button
        
        print("\nInterrupts enabled - encoder ready")
    
    def _handle_rotation(self, pin):
        """Interrupt handler for rotation"""
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_interrupt_time) > 1:  # 1ms debounce
            clk = self.clk.value()
            dt = self.dt.value()
            new_state = (clk << 1) | dt
            
            if new_state != self.last_state:
                print(f"\nInterrupt - CLK: {clk}, DT: {dt}")
                self.metrics['state_changes'] += 1
                
                # Detect direction
                if (self.last_state == 0b00 and new_state == 0b01) or \
                   (self.last_state == 0b01 and new_state == 0b11) or \
                   (self.last_state == 0b11 and new_state == 0b10) or \
                   (self.last_state == 0b10 and new_state == 0b00):
                    print("Clockwise rotation")
                    self.metrics['cw_rotations'] += 1
                    self.metrics['total_rotations'] += 1
                    self.value = min(self.value + 1, self.max_val)
                
                elif (self.last_state == 0b00 and new_state == 0b10) or \
                     (self.last_state == 0b10 and new_state == 0b11) or \
                     (self.last_state == 0b11 and new_state == 0b01) or \
                     (self.last_state == 0b01 and new_state == 0b00):
                    print("Counter-clockwise rotation")
                    self.metrics['ccw_rotations'] += 1
                    self.metrics['total_rotations'] += 1
                    self.value = max(self.value - 1, self.min_val)
                
                print(f"Value: {self.value}")
                self.last_state = new_state
            
            self.last_interrupt_time = current_time
    
    def _handle_button(self, pin):
        """Interrupt handler for button press"""
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_interrupt_time) > 50:  # 50ms debounce
            sw_val = self.sw.value()
            if not sw_val:  # Button is pressed (active low)
                print("\nButton press detected via interrupt!")
                self.metrics['button_presses'] += 1
            self.last_interrupt_time = current_time
    
    def _read_state(self):
        """Read current encoder state"""
        clk = self.clk.value()
        dt = self.dt.value()
        return (clk << 1) | dt
    
    def read(self, testing_mode=False):
        """Read encoder state with simplified detection for debugging"""
        current_time = time.ticks_ms()
        
        # Read all pins
        clk = self.clk.value()
        dt = self.dt.value()
        sw = self.sw.value()
        
        if testing_mode and time.ticks_diff(current_time, self.last_interrupt_time) >= 1000:
            # Print pin states every second in test mode
            print(f"\nPin states - CLK: {clk}, DT: {dt}, SW: {sw}")
            self.last_interrupt_time = current_time
        
        # Read current state
        current_state = (clk << 1) | dt
        
        # If state changed
        if current_state != self.last_state:
            self.metrics['state_changes'] += 1
            print(f"\nState change detected!")
            print(f"Previous state: {format_binary(self.last_state)}")
            print(f"Current state:  {format_binary(current_state)}")
            print(f"CLK: {clk}, DT: {dt}")
            
            # Simple clockwise/counter-clockwise detection
            if (self.last_state == 0b00 and current_state == 0b01) or \
               (self.last_state == 0b01 and current_state == 0b11) or \
               (self.last_state == 0b11 and current_state == 0b10) or \
               (self.last_state == 0b10 and current_state == 0b00):
                print("Clockwise rotation")
                self.metrics['cw_rotations'] += 1
                self.metrics['total_rotations'] += 1
                self.value = min(self.value + 1, self.max_val)
            
            elif (self.last_state == 0b00 and current_state == 0b10) or \
                 (self.last_state == 0b10 and current_state == 0b11) or \
                 (self.last_state == 0b11 and current_state == 0b01) or \
                 (self.last_state == 0b01 and current_state == 0b00):
                print("Counter-clockwise rotation")
                self.metrics['ccw_rotations'] += 1
                self.metrics['total_rotations'] += 1
                self.value = max(self.value - 1, self.min_val)
            
            print(f"Current value: {self.value}")
            self.last_state = current_state

def test_encoder():
    """Run comprehensive encoder tests with enhanced debugging"""
    print("\nEncoder Testing Mode")
    print("===================")
    print("Debug mode enabled - will show all state changes")
    print("Using interrupt-based detection")
    print("\nPlease perform the following tests:")
    print("a) Slow rotation (1 step per second)")
    print("b) Medium rotation (2-3 steps per second)")
    print("c) Fast rotation (as fast as possible)")
    print("d) Several button presses")
    print("\nTest duration: 30 seconds")
    print("Starting in 3 seconds...")
    time.sleep(3)
    
    tester = EncoderTester()
    end_time = time.ticks_add(time.ticks_ms(), 30000)
    
    try:
        while time.ticks_diff(end_time, time.ticks_ms()) > 0:
            tester.read(testing_mode=True)
            time.sleep_ms(1)
        
        # Print detailed test results
        print("\nDetailed Test Results:")
        print("=====================")
        print(f"Total state changes: {tester.metrics['state_changes']}")
        print(f"Total rotations: {tester.metrics['total_rotations']}")
        print(f"Clockwise rotations: {tester.metrics['cw_rotations']}")
        print(f"Counter-clockwise rotations: {tester.metrics['ccw_rotations']}")
        print(f"Button presses: {tester.metrics['button_presses']}")
        print(f"Bounce events: {tester.metrics['bounce_events']}")
            
    except KeyboardInterrupt:
        print("\nTest ended by user")

def main():
    print("Rotary Encoder Test")
    print("------------------")
    print("1. Normal mode")
    print("2. Test mode (with debugging)")
    
    try:
        choice = input("Select mode (1/2): ")
        if choice == "2":
            test_encoder()
        else:
            tester = EncoderTester()
            print("\nNormal mode started. Press Ctrl+C to exit.")
            while True:
                tester.read()
                time.sleep_ms(1)
                
    except KeyboardInterrupt:
        print("\nProgram ended by user")

if __name__ == "__main__":
    main() 
#include <Arduino.h>
#include "hal/hal.h"

#include "ui/ui.h"

void setup() {
    // Initialize Hardware and LVGL
    hal_setup();
    
    // Create UI
    ui_init();
}

void loop() {
    // Handle LVGL and Hardware tasks
    hal_loop();
    
    delay(5);
}

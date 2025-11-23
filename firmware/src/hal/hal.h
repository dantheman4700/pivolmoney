#pragma once

#include <Arduino.h>
#include <lvgl.h>

// Initialize Hardware and LVGL
void hal_setup();

// Handle Hardware and LVGL tasks
void hal_loop();

// Get Display Dimensions
#define SCREEN_WIDTH 480
#define SCREEN_HEIGHT 320

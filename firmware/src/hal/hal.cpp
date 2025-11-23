#include "hal.h"
#include <TFT_eSPI.h>
#include <Wire.h>
#include <FT6236.h>

// Hardware Instances
TFT_eSPI tft = TFT_eSPI();
FT6236 ts = FT6236();

// Buffers
#define DRAW_BUF_SIZE (SCREEN_WIDTH * SCREEN_HEIGHT / 10 * (LV_COLOR_DEPTH / 8))
uint8_t draw_buf[DRAW_BUF_SIZE];

// Display Flush Callback
void my_disp_flush(lv_display_t * disp, const lv_area_t * area, uint8_t * px_map) {
    uint32_t w = (area->x2 - area->x1 + 1);
    uint32_t h = (area->y2 - area->y1 + 1);

    tft.startWrite();
    tft.setAddrWindow(area->x1, area->y1, w, h);
    tft.pushColors((uint16_t *)px_map, w * h, true);
    tft.endWrite();

    lv_display_flush_ready(disp);
}

// Touch Read Callback
void my_touch_read(lv_indev_t * indev, lv_indev_data_t * data) {
    if (ts.touched()) {
        TS_Point p = ts.getPoint();
        data->state = LV_INDEV_STATE_PRESSED;
        // Map coordinates if needed (ILI9488 usually needs mapping depending on rotation)
        // For now assume 1:1 mapping with rotation 0
        data->point.x = p.x;
        data->point.y = p.y;
    } else {
        data->state = LV_INDEV_STATE_RELEASED;
    }
}

// Encoder State
volatile int32_t encoder_count = 0;
volatile bool encoder_btn_pressed = false;

void isr_encoder_clk() {
    if (digitalRead(20) == digitalRead(21)) {
        encoder_count++;
    } else {
        encoder_count--;
    }
}

void isr_encoder_btn() {
    encoder_btn_pressed = !digitalRead(22); // Active Low
}

// Encoder Read Callback
void my_encoder_read(lv_indev_t * indev, lv_indev_data_t * data) {
    data->enc_diff = encoder_count;
    encoder_count = 0;

    if (encoder_btn_pressed) {
        data->state = LV_INDEV_STATE_PRESSED;
    } else {
        data->state = LV_INDEV_STATE_RELEASED;
    }
}

void hal_setup() {
    // Serial
    Serial.begin(115200);
    
    // Display
    tft.init();
    tft.setRotation(0);
    tft.fillScreen(TFT_BLACK);

    // Touch
    Wire.setSDA(0);
    Wire.setSCL(1);
    Wire.begin();
    if (!ts.begin(40)) {
         Serial.println("Touch init failed!");
    }

    // LVGL
    lv_init();

    // Create Display
    lv_display_t * disp = lv_display_create(SCREEN_WIDTH, SCREEN_HEIGHT);
    lv_display_set_flush_cb(disp, my_disp_flush);
    lv_display_set_buffers(disp, draw_buf, NULL, sizeof(draw_buf), LV_DISPLAY_RENDER_MODE_PARTIAL);

    // Create Input Device (Touch)
    lv_indev_t * indev_touch = lv_indev_create();
    lv_indev_set_type(indev_touch, LV_INDEV_TYPE_POINTER);
    lv_indev_set_read_cb(indev_touch, my_touch_read);

    // Rotary Encoder
    pinMode(20, INPUT_PULLUP); // CLK
    pinMode(21, INPUT_PULLUP); // DT
    pinMode(22, INPUT_PULLUP); // SW
    
    attachInterrupt(digitalPinToInterrupt(20), isr_encoder_clk, CHANGE);
    attachInterrupt(digitalPinToInterrupt(22), isr_encoder_btn, CHANGE);

    // Create Input Device (Encoder)
    lv_indev_t * indev_enc = lv_indev_create();
    lv_indev_set_type(indev_enc, LV_INDEV_TYPE_ENCODER);
    lv_indev_set_read_cb(indev_enc, my_encoder_read);
    
    // Create a group for the encoder
    lv_group_t * g = lv_group_create();
    lv_group_set_default(g);
    lv_indev_set_group(indev_enc, g);
    
    Serial.println("HAL Initialized");
}

void hal_loop() {
    lv_timer_handler();
}

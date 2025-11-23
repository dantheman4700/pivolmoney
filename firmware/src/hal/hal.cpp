#include "hal.h"
#include <TFT_eSPI.h>
#include <Wire.h>

// Hardware Instances
TFT_eSPI tft = TFT_eSPI();

// FT6236 Constants
#define FT6236_ADDR 0x38
#define FT6236_REG_NUM_TOUCHES 0x02
#define FT6236_REG_P1_XH 0x03

// Buffers
#define DRAW_BUF_SIZE (SCREEN_WIDTH * SCREEN_HEIGHT / 10)
static lv_disp_draw_buf_t draw_buf;
static lv_color_t buf1[DRAW_BUF_SIZE];

    // Display Flush Callback
void my_disp_flush(lv_disp_drv_t *disp, const lv_area_t *area, lv_color_t *color_p) {
    uint32_t w = (area->x2 - area->x1 + 1);
    uint32_t h = (area->y2 - area->y1 + 1);

    tft.startWrite();
    tft.setAddrWindow(area->x1, area->y1, w, h);
    tft.pushColors((uint16_t *)&color_p->full, w * h, true);
    tft.endWrite();

    lv_disp_flush_ready(disp);
}

// Manual FT6236 Read
bool ft6236_read(int16_t *x, int16_t *y) {
    Wire.beginTransmission(FT6236_ADDR);
    Wire.write(FT6236_REG_NUM_TOUCHES);
    if (Wire.endTransmission() != 0) return false;

    if (Wire.requestFrom(FT6236_ADDR, 1) != 1) return false;
    uint8_t touches = Wire.read();

    if (touches > 0 && touches <= 2) {
        Wire.beginTransmission(FT6236_ADDR);
        Wire.write(FT6236_REG_P1_XH);
        Wire.endTransmission();
        
        if (Wire.requestFrom(FT6236_ADDR, 4) == 4) {
            uint8_t xh = Wire.read();
            uint8_t xl = Wire.read();
            uint8_t yh = Wire.read();
            uint8_t yl = Wire.read();
            
            *x = ((xh & 0x0F) << 8) | xl;
            *y = ((yh & 0x0F) << 8) | yl;
            return true;
        }
    }
    return false;
}

// Touch Read Callback
void my_touch_read(lv_indev_drv_t * indev_driver, lv_indev_data_t * data) {
    int16_t x, y;
    if (ft6236_read(&x, &y)) {
        data->state = LV_INDEV_STATE_PR;
        data->point.x = x;
        data->point.y = y;
    } else {
        data->state = LV_INDEV_STATE_REL;
    }
}

// Encoder State
volatile int32_t encoder_count = 0;
volatile bool encoder_btn_pressed = false;

void isr_encoder_clk() {
    if (digitalRead(ROT_CLK) == digitalRead(ROT_DT)) {
        encoder_count++;
    } else {
        encoder_count--;
    }
}

void isr_encoder_btn() {
    encoder_btn_pressed = !digitalRead(ROT_SW); // Active Low
}

// Encoder Read Callback
void my_encoder_read(lv_indev_drv_t * indev_driver, lv_indev_data_t * data) {
    data->enc_diff = encoder_count;
    encoder_count = 0;

    if (encoder_btn_pressed) {
        data->state = LV_INDEV_STATE_PR;
    } else {
        data->state = LV_INDEV_STATE_REL;
    }
}

void hal_setup() {
    // Serial
    Serial.begin(115200);
    pinMode(LED_BUILTIN, OUTPUT);
    
    // Display
    tft.init();
    tft.setRotation(1); // Landscape
    tft.fillScreen(TFT_BLACK);
    
    // Ensure Backlight is on
    pinMode(TFT_BL, OUTPUT);
    digitalWrite(TFT_BL, HIGH);

    // Touch
#ifdef ARDUINO_ARCH_ESP32
    Wire.begin(TOUCH_SDA, TOUCH_SCL);
#else
    Wire.setSDA(TOUCH_SDA);
    Wire.setSCL(TOUCH_SCL);
    Wire.begin();
#endif
    
    // LVGL
    lv_init();

    // Initialize Display Driver
    lv_disp_draw_buf_init(&draw_buf, buf1, NULL, DRAW_BUF_SIZE);

    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = SCREEN_WIDTH;
    disp_drv.ver_res = SCREEN_HEIGHT;
    disp_drv.flush_cb = my_disp_flush;
    disp_drv.draw_buf = &draw_buf;
    lv_disp_drv_register(&disp_drv);

    // Initialize Input Device (Touch)
    static lv_indev_drv_t indev_touch;
    lv_indev_drv_init(&indev_touch);
    indev_touch.type = LV_INDEV_TYPE_POINTER;
    indev_touch.read_cb = my_touch_read;
    lv_indev_drv_register(&indev_touch);

    // Rotary Encoder
    pinMode(ROT_CLK, INPUT_PULLUP); // CLK
    pinMode(ROT_DT, INPUT_PULLUP); // DT
    pinMode(ROT_SW, INPUT_PULLUP); // SW
    
    attachInterrupt(digitalPinToInterrupt(ROT_CLK), isr_encoder_clk, CHANGE);
    attachInterrupt(digitalPinToInterrupt(ROT_SW), isr_encoder_btn, CHANGE);

    // Initialize Input Device (Encoder)
    static lv_indev_drv_t indev_enc;
    lv_indev_drv_init(&indev_enc);
    indev_enc.type = LV_INDEV_TYPE_ENCODER;
    indev_enc.read_cb = my_encoder_read;
    lv_indev_t * enc_dev = lv_indev_drv_register(&indev_enc);
    
    // Create a group for the encoder
    lv_group_t * g = lv_group_create();
    lv_group_set_default(g);
    lv_indev_set_group(enc_dev, g);
    
    Serial.println("HAL Initialized");
}

void hal_loop() {
    lv_timer_handler();
    
    // Heartbeat
    static uint32_t last_blink = 0;
    if (millis() - last_blink > 1000) {
        last_blink = millis();
        digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    }
}

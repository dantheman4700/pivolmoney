#include <Arduino.h>
#include <TFT_eSPI.h>
#include <lvgl.h>

// --- Hardware & Display ---
TFT_eSPI tft = TFT_eSPI();
#define SCREEN_WIDTH 480
#define SCREEN_HEIGHT 320
static lv_disp_draw_buf_t draw_buf;
static lv_color_t buf[SCREEN_WIDTH * 10];

// --- UI ---
lv_obj_t* status_label;
lv_obj_t* app_list_label;

// --- Serial ---
String inputBuffer;

// --- Flush Callback ---
void my_disp_flush(lv_disp_drv_t *disp, const lv_area_t *area, lv_color_t *color_p) {
    uint32_t w = (area->x2 - area->x1 + 1);
    uint32_t h = (area->y2 - area->y1 + 1);

    tft.startWrite();
    tft.setAddrWindow(area->x1, area->y1, w, h);
    tft.pushPixels((uint16_t *)&color_p->full, w * h);
    tft.endWrite();

    lv_disp_flush_ready(disp);
}

// --- Force UI Update ---
void updateUI() {
    lv_refr_now(NULL);
}

// --- Text Protocol Parser ---
void processLine(String& line) {
    line.trim();
    
    if (line.startsWith("CONN")) {
        Serial.println("ACK");
        lv_label_set_text(status_label, "PC Connected");
        updateUI();
    }
    else if (line.startsWith("UPD|")) {
        String payload = line.substring(4);
        
        // Simple display: show raw payload
        lv_label_set_text(app_list_label, payload.c_str());
        lv_label_set_text(status_label, "Got Update");
        updateUI();
    }
}

void setup() {
    Serial.begin(115200);
    inputBuffer.reserve(1024);
    
    // Hardware Init
    pinMode(TFT_BL, OUTPUT);
    digitalWrite(TFT_BL, HIGH);

    tft.init();
    tft.setRotation(1);
    tft.fillScreen(TFT_BLACK);

    // LVGL Init
    lv_init();
    lv_disp_draw_buf_init(&draw_buf, buf, NULL, SCREEN_WIDTH * 10);

    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = SCREEN_WIDTH;
    disp_drv.ver_res = SCREEN_HEIGHT;
    disp_drv.flush_cb = my_disp_flush;
    disp_drv.draw_buf = &draw_buf;
    lv_disp_drv_register(&disp_drv);

    // UI Setup
    lv_obj_t* scr = lv_scr_act();
    
    status_label = lv_label_create(scr);
    lv_label_set_text(status_label, "Ready - Waiting for PC");
    lv_obj_align(status_label, LV_ALIGN_TOP_MID, 0, 10);
    lv_obj_set_style_text_color(status_label, lv_color_white(), 0);

    app_list_label = lv_label_create(scr);
    lv_label_set_text(app_list_label, "No apps yet");
    lv_obj_align(app_list_label, LV_ALIGN_CENTER, 0, 0);
    lv_obj_set_style_text_color(app_list_label, lv_color_white(), 0);
    
    // Force initial render
    lv_refr_now(NULL);
    
    Serial.println("SETUP DONE");
}

void loop() {
    lv_timer_handler();
    
    // Process serial
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n') {
            if (inputBuffer.length() > 0) {
                processLine(inputBuffer);
                inputBuffer = "";
            }
        } 
        else if (c != '\r') {
            if (inputBuffer.length() < 1000) inputBuffer += c;
        }
    }
    
    delay(5);
}

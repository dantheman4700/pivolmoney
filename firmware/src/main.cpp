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

// --- Serial Buffer (Static - NO HEAP) ---
static char inputBuffer[512];
static int bufferIndex = 0;

// --- Rate Limiting ---
static uint32_t lastUIUpdate = 0;
#define UI_UPDATE_MIN_MS 200

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

// --- Force UI Update (Rate Limited) ---
void updateUI() {
    if (millis() - lastUIUpdate > UI_UPDATE_MIN_MS) {
        lv_refr_now(NULL);
        lastUIUpdate = millis();
    }
}

// --- Text Protocol Parser ---
void processLine(const char* line) {
    if (strncmp(line, "CONN", 4) == 0) {
        Serial.println("ACK");
        lv_label_set_text(status_label, "PC Connected");
        lv_refr_now(NULL);
    }
    else if (strncmp(line, "UPD|", 4) == 0) {
        static int update_count = 0;
        update_count++;
        
        // Count commas to get app count
        int app_count = 1;
        const char* p = line;
        while (*p) {
            if (*p == ',') app_count++;
            p++;
        }
        
        char displayBuf[64];
        snprintf(displayBuf, sizeof(displayBuf), "Update #%d\n%d apps", update_count, app_count);
        lv_label_set_text(app_list_label, displayBuf);
        lv_label_set_text(status_label, "Connected");
        lv_refr_now(NULL);
    }
}

void setup() {
    Serial.begin(115200);
    
    pinMode(TFT_BL, OUTPUT);
    digitalWrite(TFT_BL, HIGH);

    tft.init();
    tft.setRotation(1);
    tft.fillScreen(TFT_BLACK);

    lv_init();
    lv_disp_draw_buf_init(&draw_buf, buf, NULL, SCREEN_WIDTH * 10);

    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = SCREEN_WIDTH;
    disp_drv.ver_res = SCREEN_HEIGHT;
    disp_drv.flush_cb = my_disp_flush;
    disp_drv.draw_buf = &draw_buf;
    lv_disp_drv_register(&disp_drv);

    lv_obj_t* scr = lv_scr_act();
    lv_obj_set_style_bg_color(scr, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);
    
    status_label = lv_label_create(scr);
    lv_label_set_text(status_label, "Ready - Waiting for PC");
    lv_obj_align(status_label, LV_ALIGN_TOP_MID, 0, 10);
    lv_obj_set_style_text_color(status_label, lv_color_white(), 0);

    app_list_label = lv_label_create(scr);
    lv_label_set_text(app_list_label, "No apps yet");
    lv_obj_align(app_list_label, LV_ALIGN_CENTER, 0, 0);
    lv_obj_set_style_text_color(app_list_label, lv_color_white(), 0);
    
    lv_refr_now(NULL);
    Serial.println("SETUP DONE");
}

void loop() {
    lv_timer_handler();
    
    // Send heartbeat every 2 seconds to keep Python happy
    static uint32_t lastHeartbeat = 0;
    if (millis() - lastHeartbeat > 2000) {
        Serial.println("HB");
        lastHeartbeat = millis();
    }
    
    // Process serial using static buffer (NO heap operations)
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n') {
            if (bufferIndex > 0) {
                inputBuffer[bufferIndex] = '\0';
                processLine(inputBuffer);
                bufferIndex = 0;
            }
        } 
        else if (c != '\r' && bufferIndex < 510) {
            inputBuffer[bufferIndex++] = c;
        }
    }
    
    delay(5);
}

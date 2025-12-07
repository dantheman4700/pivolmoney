#include <Arduino.h>
#include <TFT_eSPI.h>
#include <lvgl.h>
#include <Wire.h>

// --- Hardware & Display ---
TFT_eSPI tft = TFT_eSPI();
#define SCREEN_WIDTH 480
#define SCREEN_HEIGHT 320
static lv_disp_draw_buf_t draw_buf;
static lv_color_t buf[SCREEN_WIDTH * 10];

// --- Touch (Raw I2C - FT6336) ---
#define TOUCH_ADDR 0x38
static lv_indev_drv_t indev_drv;

bool readTouch(int* x, int* y) {
    Wire.beginTransmission(TOUCH_ADDR);
    Wire.write(0x02);
    if (Wire.endTransmission(false) != 0) return false;
    
    Wire.requestFrom(TOUCH_ADDR, 6);
    if (Wire.available() < 6) return false;
    
    uint8_t touches = Wire.read();
    uint8_t xH = Wire.read();
    uint8_t xL = Wire.read();
    uint8_t yH = Wire.read();
    uint8_t yL = Wire.read();
    Wire.read(); // Discard 6th byte
    
    // Check for touch event - xH upper nibble 0x80 = press, or touches count 1-2
    bool isTouching = ((xH & 0xC0) == 0x80) || ((touches & 0x0F) >= 1 && (touches & 0x0F) <= 2);
    if (!isTouching) return false;
    
    // Parse coordinates (lower 4 bits of xH/yH are high bits)
    int rawX = ((xH & 0x0F) << 8) | xL;
    int rawY = ((yH & 0x0F) << 8) | yL;
    
    // Apply rotation for landscape mode (rotation 1)
    *x = rawY;
    *y = SCREEN_HEIGHT - 1 - rawX;
    
    return true;
}

void touch_read_cb(lv_indev_drv_t* drv, lv_indev_data_t* data) {
    int x, y;
    if (readTouch(&x, &y)) {
        // Clamp to screen bounds
        if (x < 0) x = 0;
        if (x >= SCREEN_WIDTH) x = SCREEN_WIDTH - 1;
        if (y < 0) y = 0;
        if (y >= SCREEN_HEIGHT) y = SCREEN_HEIGHT - 1;
        
        data->point.x = x;
        data->point.y = y;
        data->state = LV_INDEV_STATE_PRESSED;
        
        static uint32_t lastPrint = 0;
        if (millis() - lastPrint > 200) {
            Serial.printf("TOUCH: x=%d, y=%d\n", x, y);
            lastPrint = millis();
        }
    } else {
        data->state = LV_INDEV_STATE_RELEASED;
    }
}

// --- App Data Storage ---
#define MAX_APPS 8
struct AppInfo {
    char name[24];
    int volume;
};
static AppInfo apps[MAX_APPS];
static int appCount = 0;
static int selectedApp = 0;

// --- Rotary Encoder ---
volatile int encoderPos = 0;
volatile int lastEncoderPos = 0;

void IRAM_ATTR encoderISR() {
    static int lastA = HIGH;
    int a = digitalRead(ROT_CLK);
    int b = digitalRead(ROT_DT);
    
    if (a != lastA) {
        if (b != a) {
            encoderPos++;
        } else {
            encoderPos--;
        }
        lastA = a;
    }
}

// --- UI Elements ---
lv_obj_t* status_label;
lv_obj_t* app_list_container;
lv_obj_t* app_buttons[MAX_APPS];  // Buttons instead of labels
lv_obj_t* volume_bar;
lv_obj_t* selected_app_label;

// --- Serial Buffer ---
static char inputBuffer[512];
static int bufferIndex = 0;

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

// --- App Button Click Handler ---
void app_btn_event_cb(lv_event_t* e) {
    lv_obj_t* btn = lv_event_get_target(e);
    int idx = (int)(intptr_t)lv_obj_get_user_data(btn);
    
    if (idx >= 0 && idx < appCount) {
        selectedApp = idx;
        
        // Update UI to show selection
        for (int i = 0; i < MAX_APPS; i++) {
            if (app_buttons[i]) {
                if (i == selectedApp) {
                    lv_obj_set_style_bg_color(app_buttons[i], lv_color_hex(0x003300), 0);
                    lv_obj_set_style_border_color(app_buttons[i], lv_color_hex(0x00FF00), 0);
                } else {
                    lv_obj_set_style_bg_color(app_buttons[i], lv_color_hex(0x1a1a1a), 0);
                    lv_obj_set_style_border_color(app_buttons[i], lv_color_hex(0x333333), 0);
                }
            }
        }
        
        // Update volume display
        if (appCount > 0 && selectedApp < appCount) {
            lv_bar_set_value(volume_bar, apps[selectedApp].volume, LV_ANIM_ON);
            char volLabel[48];
            snprintf(volLabel, sizeof(volLabel), "%s: %d%%", apps[selectedApp].name, apps[selectedApp].volume);
            lv_label_set_text(selected_app_label, volLabel);
        }
        
        lv_refr_now(NULL);
    }
}

// --- Update App List Display ---
void updateAppListUI() {
    for (int i = 0; i < MAX_APPS; i++) {
        if (i < appCount && app_buttons[i]) {
            lv_obj_t* label = lv_obj_get_child(app_buttons[i], 0);
            if (label) {
                char buf[32];
                snprintf(buf, sizeof(buf), "%s: %d%%", apps[i].name, apps[i].volume);
                lv_label_set_text(label, buf);
            }
            
            // Highlight selected
            if (i == selectedApp) {
                lv_obj_set_style_bg_color(app_buttons[i], lv_color_hex(0x003300), 0);
                lv_obj_set_style_border_color(app_buttons[i], lv_color_hex(0x00FF00), 0);
            } else {
                lv_obj_set_style_bg_color(app_buttons[i], lv_color_hex(0x1a1a1a), 0);
                lv_obj_set_style_border_color(app_buttons[i], lv_color_hex(0x333333), 0);
            }
            
            lv_obj_clear_flag(app_buttons[i], LV_OBJ_FLAG_HIDDEN);
        } else if (app_buttons[i]) {
            lv_obj_add_flag(app_buttons[i], LV_OBJ_FLAG_HIDDEN);
        }
    }
    
    // Update volume bar for selected app
    if (appCount > 0 && selectedApp < appCount) {
        lv_bar_set_value(volume_bar, apps[selectedApp].volume, LV_ANIM_ON);
        char volLabel[48];
        snprintf(volLabel, sizeof(volLabel), "%s: %d%%", apps[selectedApp].name, apps[selectedApp].volume);
        lv_label_set_text(selected_app_label, volLabel);
    }
    
    lv_refr_now(NULL);
}

// --- Parse Update Message ---
void parseUpdate(const char* payload) {
    appCount = 0;
    const char* start = payload;
    const char* p = payload;
    
    while (*p && appCount < MAX_APPS) {
        if (*p == ',' || *(p+1) == '\0') {
            int tokenLen = (*p == ',') ? (p - start) : (p - start + 1);
            
            if (tokenLen > 0 && tokenLen < 48) {
                char token[48];
                strncpy(token, start, tokenLen);
                token[tokenLen] = '\0';
                
                char* colon = strchr(token, ':');
                if (colon) {
                    *colon = '\0';
                    strncpy(apps[appCount].name, token, 23);
                    apps[appCount].name[23] = '\0';
                    apps[appCount].volume = atoi(colon + 1);
                    appCount++;
                }
            }
            start = p + 1;
        }
        p++;
    }
    
    // Clamp selection
    if (selectedApp >= appCount) selectedApp = appCount - 1;
    if (selectedApp < 0) selectedApp = 0;
}

// --- Process Serial Line ---
void processLine(const char* line) {
    if (strncmp(line, "CONN", 4) == 0) {
        Serial.println("ACK");
        lv_label_set_text(status_label, "PC Connected");
        lv_refr_now(NULL);
    }
    else if (strncmp(line, "UPD|", 4) == 0) {
        parseUpdate(line + 4);
        
        char statusBuf[32];
        snprintf(statusBuf, sizeof(statusBuf), "Connected - %d apps", appCount);
        lv_label_set_text(status_label, statusBuf);
        
        updateAppListUI();
    }
}

// --- Setup UI Elements ---
void createUI() {
    lv_obj_t* scr = lv_scr_act();
    lv_obj_set_style_bg_color(scr, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);
    
    // Status bar at top
    status_label = lv_label_create(scr);
    lv_label_set_text(status_label, "Ready - Waiting for PC");
    lv_obj_align(status_label, LV_ALIGN_TOP_MID, 0, 5);
    lv_obj_set_style_text_color(status_label, lv_color_hex(0x888888), 0);
    
    // App list on left side - scrollable container
    app_list_container = lv_obj_create(scr);
    lv_obj_set_size(app_list_container, 220, 290);
    lv_obj_align(app_list_container, LV_ALIGN_LEFT_MID, 5, 15);
    lv_obj_set_style_bg_color(app_list_container, lv_color_black(), 0);
    lv_obj_set_style_border_width(app_list_container, 2, 0);
    lv_obj_set_style_border_color(app_list_container, lv_color_white(), 0);
    lv_obj_set_style_pad_all(app_list_container, 5, 0);
    lv_obj_set_flex_flow(app_list_container, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(app_list_container, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_START);
    lv_obj_set_style_pad_row(app_list_container, 5, 0);
    
    // Create app buttons (larger, touchable)
    for (int i = 0; i < MAX_APPS; i++) {
        app_buttons[i] = lv_btn_create(app_list_container);
        lv_obj_set_size(app_buttons[i], 200, 32);  // Larger for touch
        lv_obj_set_user_data(app_buttons[i], (void*)(intptr_t)i);
        lv_obj_add_event_cb(app_buttons[i], app_btn_event_cb, LV_EVENT_CLICKED, NULL);
        
        // Style
        lv_obj_set_style_bg_color(app_buttons[i], lv_color_hex(0x1a1a1a), 0);
        lv_obj_set_style_border_width(app_buttons[i], 1, 0);
        lv_obj_set_style_border_color(app_buttons[i], lv_color_hex(0x333333), 0);
        lv_obj_set_style_radius(app_buttons[i], 5, 0);
        
        // Label inside button
        lv_obj_t* label = lv_label_create(app_buttons[i]);
        lv_label_set_text(label, "");
        lv_obj_center(label);
        lv_obj_set_style_text_color(label, lv_color_white(), 0);
        
        lv_obj_add_flag(app_buttons[i], LV_OBJ_FLAG_HIDDEN);
    }
    
    // Volume display on right side
    lv_obj_t* vol_container = lv_obj_create(scr);
    lv_obj_set_size(vol_container, 240, 290);
    lv_obj_align(vol_container, LV_ALIGN_RIGHT_MID, -5, 15);
    lv_obj_set_style_bg_color(vol_container, lv_color_black(), 0);
    lv_obj_set_style_border_width(vol_container, 2, 0);
    lv_obj_set_style_border_color(vol_container, lv_color_white(), 0);
    lv_obj_set_style_pad_all(vol_container, 15, 0);
    
    // Title label
    lv_obj_t* title = lv_label_create(vol_container);
    lv_label_set_text(title, "SELECTED APP");
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 5);
    lv_obj_set_style_text_color(title, lv_color_white(), 0);
    
    // Selected app name + volume
    selected_app_label = lv_label_create(vol_container);
    lv_label_set_text(selected_app_label, "Tap app to select");
    lv_obj_align(selected_app_label, LV_ALIGN_TOP_MID, 0, 30);
    lv_obj_set_style_text_color(selected_app_label, lv_color_hex(0x00FF00), 0);
    
    // Volume bar label
    lv_obj_t* bar_label = lv_label_create(vol_container);
    lv_label_set_text(bar_label, "Volume:");
    lv_obj_align(bar_label, LV_ALIGN_LEFT_MID, 10, -20);
    lv_obj_set_style_text_color(bar_label, lv_color_white(), 0);
    
    // Volume bar
    volume_bar = lv_bar_create(vol_container);
    lv_obj_set_size(volume_bar, 180, 25);
    lv_obj_align(volume_bar, LV_ALIGN_CENTER, 0, 10);
    lv_bar_set_range(volume_bar, 0, 100);
    lv_bar_set_value(volume_bar, 0, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(volume_bar, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_bg_color(volume_bar, lv_color_hex(0x00AA00), LV_PART_INDICATOR);
    
    // Instructions
    lv_obj_t* help_label = lv_label_create(vol_container);
    lv_label_set_text(help_label, "Tap: Select app\nTurn dial: Adjust volume");
    lv_obj_align(help_label, LV_ALIGN_BOTTOM_MID, 0, -10);
    lv_obj_set_style_text_color(help_label, lv_color_white(), 0);
}

void setup() {
    Serial.begin(115200);
    delay(500);
    
    Serial.println("\n=== VOLUME PANEL BOOT ===");
    
    // Touch reset pin
    pinMode(TOUCH_RST, OUTPUT);
    digitalWrite(TOUCH_RST, LOW);
    delay(10);
    digitalWrite(TOUCH_RST, HIGH);
    delay(100);
    
    // Initialize I2C for touch
    Wire.begin(TOUCH_SDA, TOUCH_SCL);
    Wire.setClock(400000);
    Serial.println("Touch I2C initialized");
    
    // Encoder pins
    pinMode(ROT_CLK, INPUT_PULLUP);
    pinMode(ROT_DT, INPUT_PULLUP);
    pinMode(ROT_SW, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(ROT_CLK), encoderISR, CHANGE);
    
    // Display
    pinMode(TFT_BL, OUTPUT);
    digitalWrite(TFT_BL, HIGH);
    tft.init();
    tft.setRotation(1);
    tft.fillScreen(TFT_BLACK);

    // LVGL
    lv_init();
    lv_disp_draw_buf_init(&draw_buf, buf, NULL, SCREEN_WIDTH * 10);

    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = SCREEN_WIDTH;
    disp_drv.ver_res = SCREEN_HEIGHT;
    disp_drv.flush_cb = my_disp_flush;
    disp_drv.draw_buf = &draw_buf;
    lv_disp_drv_register(&disp_drv);
    
    // Touch input device
    lv_indev_drv_init(&indev_drv);
    indev_drv.type = LV_INDEV_TYPE_POINTER;
    indev_drv.read_cb = touch_read_cb;
    lv_indev_drv_register(&indev_drv);

    createUI();
    lv_refr_now(NULL);
    Serial.println("SETUP DONE");
}

void loop() {
    lv_timer_handler();
    
    // Direct touch polling for app selection
    static uint32_t lastTouchPoll = 0;
    static bool wasTouching = false;
    
    if (millis() - lastTouchPoll > 50) {  // Poll every 50ms
        int tx, ty;
        bool isTouching = readTouch(&tx, &ty);
        
        // On touch start (not held)
        if (isTouching && !wasTouching) {
            Serial.printf("TOUCH: %d,%d\n", tx, ty);
            
            // Check if touch is in app list area (left side, x < 230)
            if (tx < 230 && ty > 30 && ty < 300 && appCount > 0) {
                // App list starts at y~40, each row is ~37px (32px button + 5px gap)
                int row = (ty - 40) / 37;
                if (row >= 0 && row < appCount) {
                    selectedApp = row;
                    Serial.printf("Selected app %d: %s\n", selectedApp, apps[selectedApp].name);
                    updateAppListUI();
                }
            }
        }
        
        wasTouching = isTouching;
        lastTouchPoll = millis();
    }
    
    // Heartbeat
    static uint32_t lastHeartbeat = 0;
    if (millis() - lastHeartbeat > 2000) {
        Serial.println("HB");
        lastHeartbeat = millis();
    }
    
    // Handle encoder rotation - DIRECTLY adjust volume
    if (encoderPos != lastEncoderPos) {
        int delta = encoderPos - lastEncoderPos;
        lastEncoderPos = encoderPos;
        
        if (appCount > 0 && selectedApp < appCount) {
            apps[selectedApp].volume += delta * 2; // 2% per click
            if (apps[selectedApp].volume < 0) apps[selectedApp].volume = 0;
            if (apps[selectedApp].volume > 100) apps[selectedApp].volume = 100;
            
            // Send volume change to PC
            Serial.printf("VOL|%s:%d\n", apps[selectedApp].name, apps[selectedApp].volume);
            
            updateAppListUI();
        }
    }
    
    // Process serial
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

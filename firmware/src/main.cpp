#include <Arduino.h>
#include <TFT_eSPI.h>
#include <lvgl.h>
#include <Wire.h>

// --- Hardware & Display ---
TFT_eSPI tft = TFT_eSPI();
#define SCREEN_WIDTH 480
#define SCREEN_HEIGHT 320
static lv_disp_draw_buf_t draw_buf;
static lv_color_t buf[SCREEN_WIDTH * 40];  // Larger buffer for smoother scrolling

// --- Touch (Raw I2C - FT6336) ---
#define TOUCH_ADDR 0x38
static lv_indev_drv_t indev_drv;
static lv_indev_t* touch_indev = NULL;

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
    } else {
        data->state = LV_INDEV_STATE_RELEASED;
    }
}

// --- App Data Storage ---
#define MAX_APPS 8
#define ICON_SIZE 32
#define ICON_PIXELS (ICON_SIZE * ICON_SIZE)

struct AppInfo {
    char name[24];
    int volume;
    bool hasIcon;
    lv_color_t iconData[ICON_PIXELS];  // 32x32 RGB565 icon
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
lv_obj_t* app_buttons[MAX_APPS];
lv_obj_t* app_icons[MAX_APPS];         // Icon images in rows
lv_obj_t* app_labels_ui[MAX_APPS];     // Labels in rows
lv_obj_t* volume_bar;
lv_obj_t* selected_app_label;
lv_obj_t* selected_app_icon;           // Large icon on right panel

// Icon image descriptors
lv_img_dsc_t icon_descriptors[MAX_APPS];
lv_img_dsc_t selected_icon_dsc;

// --- Serial Buffer (large enough for icon base64 data ~2800 bytes) ---
static char inputBuffer[4096];
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

// Forward declaration
void updateAppListUI();

// --- App Button Click Handler ---
void app_btn_event_cb(lv_event_t* e) {
    lv_obj_t* btn = lv_event_get_target(e);
    int idx = (int)(intptr_t)lv_obj_get_user_data(btn);
    
    if (idx >= 0 && idx < appCount) {
        selectedApp = idx;
        Serial.printf("Selected: %s\n", apps[selectedApp].name);
        updateAppListUI();
    }
}

// --- Update App List Display ---
void updateAppListUI() {
    for (int i = 0; i < MAX_APPS; i++) {
        if (i < appCount && app_buttons[i]) {
            // Update label text
            char buf[32];
            snprintf(buf, sizeof(buf), "%s: %d%%", apps[i].name, apps[i].volume);
            lv_label_set_text(app_labels_ui[i], buf);
            
            // Update icon if available
            // Update icon if available
            if (apps[i].hasIcon) {
                icon_descriptors[i].header.cf = LV_IMG_CF_TRUE_COLOR;
                icon_descriptors[i].header.w = ICON_SIZE;
                icon_descriptors[i].header.h = ICON_SIZE;
                icon_descriptors[i].data_size = ICON_PIXELS * sizeof(lv_color_t);
                icon_descriptors[i].data = (const uint8_t*)apps[i].iconData;
                lv_img_set_src(app_icons[i], &icon_descriptors[i]);
            } else {
                // No icon? Show a generic symbol or transparent
                // For now, just clear it or set to a placeholder if you have one
                // Or since data is 0-filled, it shows black.
                // But we must ensure the invalidation happens if it was previously set.
                // Just let it be black/empty for now, but ensure we don't leave old pointers if dynamic
                // Actually, if we memset 0, it should be black.
                // But let's set a placeholder to be sure 
                // lv_img_set_src(app_icons[i], LV_SYMBOL_AUDIO); // Optional: use built-in symbol
                
                // If we want it to be empty/invisible but take space:
                // It currently points to apps[i].iconData which is 0s.
                // So it should be black.
                // Force update?
                lv_obj_invalidate(app_icons[i]); 
            }
            
            // Highlight selected
            if (i == selectedApp) {
                lv_obj_set_style_bg_color(app_buttons[i], lv_color_hex(0x003300), 0);
                lv_obj_set_style_border_color(app_buttons[i], lv_color_hex(0x00FF00), 0);
                lv_obj_set_style_border_width(app_buttons[i], 2, 0);
            } else {
                lv_obj_set_style_bg_color(app_buttons[i], lv_color_hex(0x1a1a1a), 0);
                lv_obj_set_style_border_color(app_buttons[i], lv_color_hex(0x333333), 0);
                lv_obj_set_style_border_width(app_buttons[i], 1, 0);
            }
            
            lv_obj_clear_flag(app_buttons[i], LV_OBJ_FLAG_HIDDEN);
        } else if (app_buttons[i]) {
            lv_obj_add_flag(app_buttons[i], LV_OBJ_FLAG_HIDDEN);
        }
    }
    
    // Update selected app on right panel
    if (appCount > 0 && selectedApp < appCount) {
        lv_bar_set_value(volume_bar, apps[selectedApp].volume, LV_ANIM_ON);
        char volLabel[48];
        snprintf(volLabel, sizeof(volLabel), "%s: %d%%", apps[selectedApp].name, apps[selectedApp].volume);
        lv_label_set_text(selected_app_label, volLabel);
        
        // Update large icon
        // Update large icon
        if (apps[selectedApp].hasIcon) {
            selected_icon_dsc.header.cf = LV_IMG_CF_TRUE_COLOR;
            selected_icon_dsc.header.w = ICON_SIZE;
            selected_icon_dsc.header.h = ICON_SIZE;
            selected_icon_dsc.data_size = ICON_PIXELS * sizeof(lv_color_t);
            selected_icon_dsc.data = (const uint8_t*)apps[selectedApp].iconData;
            lv_img_set_src(selected_app_icon, &selected_icon_dsc);
            lv_img_set_zoom(selected_app_icon, 512);  // 2x zoom (64x64 display)
        } else {
            // No icon - maybe show a default symbol or just invalidate
             lv_obj_invalidate(selected_app_icon);
        }
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
                    
                    // Clear previous icon for this slot!
                    apps[appCount].hasIcon = false;
                    memset(apps[appCount].iconData, 0, sizeof(apps[appCount].iconData));
                    
                    strncpy(apps[appCount].name, token, 23);
                    apps[appCount].name[23] = '\0';
                    apps[appCount].volume = atoi(colon + 1);
                    // Serial.printf("Slot %d: %s (Icon cleared)\n", appCount, apps[appCount].name); 
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

// --- Base64 Decoding ---
static const char base64_chars[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

int base64_char_value(char c) {
    if (c >= 'A' && c <= 'Z') return c - 'A';
    if (c >= 'a' && c <= 'z') return c - 'a' + 26;
    if (c >= '0' && c <= '9') return c - '0' + 52;
    if (c == '+') return 62;
    if (c == '/') return 63;
    return -1;
}

int base64_decode(const char* input, uint8_t* output, int max_output) {
    int input_len = strlen(input);
    int output_idx = 0;
    
    for (int i = 0; i < input_len && output_idx < max_output; i += 4) {
        int v0 = base64_char_value(input[i]);
        int v1 = (i+1 < input_len) ? base64_char_value(input[i+1]) : 0;
        int v2 = (i+2 < input_len && input[i+2] != '=') ? base64_char_value(input[i+2]) : 0;
        int v3 = (i+3 < input_len && input[i+3] != '=') ? base64_char_value(input[i+3]) : 0;
        
        if (v0 < 0 || v1 < 0) break;
        
        output[output_idx++] = (v0 << 2) | (v1 >> 4);
        if (output_idx >= max_output) break;
        
        if (i+2 < input_len && input[i+2] != '=') {
            output[output_idx++] = ((v1 & 0x0F) << 4) | (v2 >> 2);
            if (output_idx >= max_output) break;
        }
        
        if (i+3 < input_len && input[i+3] != '=') {
            output[output_idx++] = ((v2 & 0x03) << 6) | v3;
        }
    }
    
    return output_idx;
}

// --- Parse Icon Message ---
void parseIcon(const char* payload) {
    // Format: AppName:Base64Data
    char* colon = strchr(payload, ':');
    if (!colon) {
        Serial.println("ICN: No colon in payload");
        return;
    }
    
    *colon = '\0';
    const char* appName = payload;
    const char* b64Data = colon + 1;
    
    Serial.printf("ICN: Looking for app '%s' (b64 len=%d)\n", appName, strlen(b64Data));
    
    // Find the app
    int appIdx = -1;
    for (int i = 0; i < appCount; i++) {
        Serial.printf("  Comparing with '%s'\n", apps[i].name);
        if (strcmp(apps[i].name, appName) == 0) {
            appIdx = i;
            break;
        }
    }
    
    if (appIdx < 0) {
        Serial.printf("ICN: App not found: '%s', have %d apps:\n", appName, appCount);
        for (int i = 0; i < appCount; i++) {
            Serial.printf("  [%d] '%s'\n", i, apps[i].name);
        }
        return;
    }
    
    // Decode base64 to icon data (STATIC to prevent stack overflow!)
    // 32x32 RGB565 = 2048 bytes (each pixel is 2 bytes)
    static uint8_t iconBytes[ICON_PIXELS * 2];
    int decoded = base64_decode(b64Data, iconBytes, sizeof(iconBytes));
    
    if (decoded != ICON_PIXELS * 2) {
        Serial.printf("ICN: Wrong size for %s: got %d, expected %d\n", appName, decoded, ICON_PIXELS * 2);
        return;
    }
    
    // Convert to lv_color_t array (handling byte order - SWAPPED)
    for (int i = 0; i < ICON_PIXELS; i++) {
        // Swap bytes: Low byte first, then High byte (because ESP32 is Little Endian)
        uint16_t rgb565 = (iconBytes[i*2+1] << 8) | iconBytes[i*2];
        apps[appIdx].iconData[i].full = rgb565;
    }
    
    apps[appIdx].hasIcon = true;
    Serial.printf("ICN: Loaded icon for %s\n", appName);
    
    // Update UI to show new icon
    updateAppListUI();
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
    else if (strncmp(line, "ICN|", 4) == 0) {
        // Make a mutable copy for parsing (STATIC to prevent stack overflow)
        static char iconPayload[4096];
        strncpy(iconPayload, line + 4, sizeof(iconPayload) - 1);
        iconPayload[sizeof(iconPayload) - 1] = '\0';
        parseIcon(iconPayload);
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
    
    // App list on left side - SCROLLABLE container
    app_list_container = lv_obj_create(scr);
    lv_obj_set_size(app_list_container, 230, 290);
    lv_obj_align(app_list_container, LV_ALIGN_LEFT_MID, 5, 15);
    lv_obj_set_style_bg_color(app_list_container, lv_color_hex(0x111111), 0);
    lv_obj_set_style_border_width(app_list_container, 2, 0);
    lv_obj_set_style_border_color(app_list_container, lv_color_white(), 0);
    lv_obj_set_style_pad_all(app_list_container, 8, 0);
    lv_obj_set_flex_flow(app_list_container, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(app_list_container, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
    lv_obj_set_style_pad_row(app_list_container, 6, 0);
    lv_obj_set_scroll_dir(app_list_container, LV_DIR_VER);  // Enable vertical scroll
    lv_obj_set_scrollbar_mode(app_list_container, LV_SCROLLBAR_MODE_AUTO);
    
    // Create app buttons with icons (larger rows: 48px height)
    for (int i = 0; i < MAX_APPS; i++) {
        app_buttons[i] = lv_btn_create(app_list_container);
        lv_obj_set_size(app_buttons[i], 205, 48);
        lv_obj_set_user_data(app_buttons[i], (void*)(intptr_t)i);
        lv_obj_add_event_cb(app_buttons[i], app_btn_event_cb, LV_EVENT_CLICKED, NULL);
        
        // Button style
        lv_obj_set_style_bg_color(app_buttons[i], lv_color_hex(0x1a1a1a), 0);
        lv_obj_set_style_border_width(app_buttons[i], 1, 0);
        lv_obj_set_style_border_color(app_buttons[i], lv_color_hex(0x333333), 0);
        lv_obj_set_style_radius(app_buttons[i], 8, 0);
        lv_obj_set_style_pad_left(app_buttons[i], 5, 0);
        lv_obj_set_style_pad_right(app_buttons[i], 5, 0);
        lv_obj_set_flex_flow(app_buttons[i], LV_FLEX_FLOW_ROW);
        lv_obj_set_flex_align(app_buttons[i], LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
        
        // Icon placeholder (32x32) - left side of button
        app_icons[i] = lv_img_create(app_buttons[i]);
        lv_obj_set_size(app_icons[i], ICON_SIZE, ICON_SIZE);
        lv_obj_set_style_bg_color(app_icons[i], lv_color_hex(0x333333), 0);
        lv_obj_set_style_bg_opa(app_icons[i], LV_OPA_COVER, 0);
        lv_obj_set_style_radius(app_icons[i], 4, 0);
        
        // App name label - right of icon
        app_labels_ui[i] = lv_label_create(app_buttons[i]);
        lv_label_set_text(app_labels_ui[i], "");
        lv_obj_set_style_text_color(app_labels_ui[i], lv_color_white(), 0);
        lv_obj_set_style_pad_left(app_labels_ui[i], 8, 0);
        
        lv_obj_add_flag(app_buttons[i], LV_OBJ_FLAG_HIDDEN);
    }
    
    // Volume display on right side
    lv_obj_t* vol_container = lv_obj_create(scr);
    lv_obj_set_size(vol_container, 230, 290);
    lv_obj_align(vol_container, LV_ALIGN_RIGHT_MID, -5, 15);
    lv_obj_set_style_bg_color(vol_container, lv_color_hex(0x111111), 0);
    lv_obj_set_style_border_width(vol_container, 2, 0);
    lv_obj_set_style_border_color(vol_container, lv_color_white(), 0);
    lv_obj_set_style_pad_all(vol_container, 15, 0);
    
    // Title label
    lv_obj_t* title = lv_label_create(vol_container);
    lv_label_set_text(title, "SELECTED APP");
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 0);
    lv_obj_set_style_text_color(title, lv_color_white(), 0);
    
    // Large icon for selected app (64x64 scaled display)
    selected_app_icon = lv_img_create(vol_container);
    // Don't set size here, let it follow content + zoom to avoid tiling
    lv_obj_align(selected_app_icon, LV_ALIGN_TOP_MID, 0, 55);
    lv_obj_set_style_bg_color(selected_app_icon, lv_color_hex(0x333333), 0);
    lv_obj_set_style_bg_opa(selected_app_icon, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(selected_app_icon, 8, 0);
    
    // Selected app name + volume
    selected_app_label = lv_label_create(vol_container);
    lv_label_set_text(selected_app_label, "Tap app to select");
    lv_obj_align(selected_app_label, LV_ALIGN_TOP_MID, 0, 100);
    lv_obj_set_style_text_color(selected_app_label, lv_color_hex(0x00FF00), 0);
    
    // Volume bar label
    lv_obj_t* bar_label = lv_label_create(vol_container);
    lv_label_set_text(bar_label, "Volume:");
    lv_obj_align(bar_label, LV_ALIGN_LEFT_MID, 5, 20);
    lv_obj_set_style_text_color(bar_label, lv_color_white(), 0);
    
    // Volume bar
    volume_bar = lv_bar_create(vol_container);
    lv_obj_set_size(volume_bar, 180, 25);
    lv_obj_align(volume_bar, LV_ALIGN_CENTER, 0, 50);
    lv_bar_set_range(volume_bar, 0, 100);
    lv_bar_set_value(volume_bar, 0, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(volume_bar, lv_color_hex(0x333333), LV_PART_MAIN);
    lv_obj_set_style_bg_color(volume_bar, lv_color_hex(0x00AA00), LV_PART_INDICATOR);
    lv_obj_set_style_radius(volume_bar, 5, 0);
    
    // Instructions
    lv_obj_t* help_label = lv_label_create(vol_container);
    lv_label_set_text(help_label, "Tap: Select | Dial: Volume");
    lv_obj_align(help_label, LV_ALIGN_BOTTOM_MID, 0, -5);
    lv_obj_set_style_text_color(help_label, lv_color_hex(0x666666), 0);
}

void setup() {
    Serial.setRxBufferSize(16384); // 16KB Buffer = holds ~6 icons pending processing
    Serial.begin(921600);
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
    lv_disp_draw_buf_init(&draw_buf, buf, NULL, SCREEN_WIDTH * 40);

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
    touch_indev = lv_indev_drv_register(&indev_drv);
    
    if (touch_indev) {
        Serial.println("Touch input registered OK");
    } else {
        Serial.println("Touch input registration FAILED!");
    }

    createUI();
    lv_refr_now(NULL);
    Serial.println("SETUP DONE");
}

void loop() {
    // LVGL tick - required for LVGL to poll input devices!
    static uint32_t lastTick = 0;
    uint32_t now = millis();
    lv_tick_inc(now - lastTick);
    lastTick = now;
    
    lv_timer_handler();
    
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
        else if (c != '\r' && bufferIndex < 4094) {
            inputBuffer[bufferIndex++] = c;
        }
    }
    
    delay(5);
}

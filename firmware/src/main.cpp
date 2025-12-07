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

// --- App Data Storage ---
#define MAX_APPS 10
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
volatile bool buttonPressed = false;

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

void IRAM_ATTR buttonISR() {
    static uint32_t lastPress = 0;
    if (millis() - lastPress > 200) { // Debounce
        buttonPressed = true;
        lastPress = millis();
    }
}

// --- UI Elements ---
lv_obj_t* status_label;
lv_obj_t* app_list_container;
lv_obj_t* app_labels[MAX_APPS];
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

// --- Update App List Display ---
void updateAppListUI() {
    for (int i = 0; i < MAX_APPS; i++) {
        if (i < appCount && app_labels[i]) {
            char buf[48];
            if (i == selectedApp) {
                snprintf(buf, sizeof(buf), "> %s: %d%%", apps[i].name, apps[i].volume);
                lv_obj_set_style_text_color(app_labels[i], lv_color_hex(0x00FF00), 0); // Green
            } else {
                snprintf(buf, sizeof(buf), "  %s: %d%%", apps[i].name, apps[i].volume);
                lv_obj_set_style_text_color(app_labels[i], lv_color_white(), 0);
            }
            lv_label_set_text(app_labels[i], buf);
            lv_obj_clear_flag(app_labels[i], LV_OBJ_FLAG_HIDDEN);
        } else if (app_labels[i]) {
            lv_obj_add_flag(app_labels[i], LV_OBJ_FLAG_HIDDEN);
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
    
    // App list on left side
    app_list_container = lv_obj_create(scr);
    lv_obj_set_size(app_list_container, 200, 280);
    lv_obj_align(app_list_container, LV_ALIGN_LEFT_MID, 10, 15);
    lv_obj_set_style_bg_color(app_list_container, lv_color_black(), 0);
    lv_obj_set_style_border_width(app_list_container, 2, 0);
    lv_obj_set_style_border_color(app_list_container, lv_color_white(), 0);
    lv_obj_set_style_pad_all(app_list_container, 10, 0);
    lv_obj_set_flex_flow(app_list_container, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(app_list_container, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
    
    // Create app labels
    for (int i = 0; i < MAX_APPS; i++) {
        app_labels[i] = lv_label_create(app_list_container);
        lv_label_set_text(app_labels[i], "");
        lv_obj_set_style_text_color(app_labels[i], lv_color_white(), 0);
        lv_obj_add_flag(app_labels[i], LV_OBJ_FLAG_HIDDEN);
    }
    
    // Volume display on right side
    lv_obj_t* vol_container = lv_obj_create(scr);
    lv_obj_set_size(vol_container, 240, 280);
    lv_obj_align(vol_container, LV_ALIGN_RIGHT_MID, -10, 15);
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
    lv_label_set_text(selected_app_label, "No app selected");
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
    lv_label_set_text(help_label, "Turn dial: Select app\nPress button: (TODO)");
    lv_obj_align(help_label, LV_ALIGN_BOTTOM_MID, 0, -10);
    lv_obj_set_style_text_color(help_label, lv_color_white(), 0);
}

void setup() {
    Serial.begin(115200);
    
    // Encoder pins
    pinMode(ROT_CLK, INPUT_PULLUP);
    pinMode(ROT_DT, INPUT_PULLUP);
    pinMode(ROT_SW, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(ROT_CLK), encoderISR, CHANGE);
    attachInterrupt(digitalPinToInterrupt(ROT_SW), buttonISR, FALLING);
    
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

    createUI();
    lv_refr_now(NULL);
    Serial.println("SETUP DONE");
}

void loop() {
    lv_timer_handler();
    
    // Heartbeat
    static uint32_t lastHeartbeat = 0;
    if (millis() - lastHeartbeat > 2000) {
        Serial.println("HB");
        lastHeartbeat = millis();
    }
    
    // Handle encoder rotation (app selection)
    if (encoderPos != lastEncoderPos) {
        int delta = encoderPos - lastEncoderPos;
        lastEncoderPos = encoderPos;
        
        selectedApp += delta;
        if (selectedApp < 0) selectedApp = appCount - 1;
        if (selectedApp >= appCount) selectedApp = 0;
        
        updateAppListUI();
    }
    
    // Handle button press
    if (buttonPressed) {
        buttonPressed = false;
        Serial.println("BUTTON PRESSED!");
        if (appCount > 0 && selectedApp < appCount) {
            Serial.printf("BTN|%s\n", apps[selectedApp].name);
        }
    }
    
    // Debug: Check button state every 500ms
    static uint32_t lastBtnCheck = 0;
    static int lastBtnState = HIGH;
    int btnState = digitalRead(ROT_SW);
    if (btnState != lastBtnState) {
        Serial.printf("Button state: %d\n", btnState);
        lastBtnState = btnState;
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

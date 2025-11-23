#include "ui.h"
#include "media_screen.h"
#include "volume_screen.h"

void ui_init() {
    // Create screens
    ui_create_media_screen();
    ui_create_volume_screen();

    // Load initial screen
    lv_scr_load(ui_get_media_screen());
}

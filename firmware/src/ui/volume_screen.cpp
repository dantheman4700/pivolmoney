#include "volume_screen.h"

static lv_obj_t * volume_screen = NULL;

void ui_create_volume_screen() {
    volume_screen = lv_obj_create(NULL);
    
    // Master Volume Slider
    lv_obj_t * slider_master = lv_slider_create(volume_screen);
    lv_obj_set_size(slider_master, 20, 200);
    lv_obj_align(slider_master, LV_ALIGN_LEFT_MID, 40, 0);
    lv_slider_set_value(slider_master, 50, LV_ANIM_OFF);
    
    lv_obj_t * label_master = lv_label_create(volume_screen);
    lv_label_set_text(label_master, "Master");
    lv_obj_align_to(label_master, slider_master, LV_ALIGN_OUT_BOTTOM_MID, 0, 10);

    // App Volume Slider (Example)
    lv_obj_t * slider_app = lv_slider_create(volume_screen);
    lv_obj_set_size(slider_app, 20, 200);
    lv_obj_align(slider_app, LV_ALIGN_RIGHT_MID, -40, 0);
    lv_slider_set_value(slider_app, 75, LV_ANIM_OFF);

    lv_obj_t * label_app = lv_label_create(volume_screen);
    lv_label_set_text(label_app, "App");
    lv_obj_align_to(label_app, slider_app, LV_ALIGN_OUT_BOTTOM_MID, 0, 10);
}

lv_obj_t* ui_get_volume_screen() {
    if (!volume_screen) {
        ui_create_volume_screen();
    }
    return volume_screen;
}

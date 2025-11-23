#include "media_screen.h"

static lv_obj_t * media_screen = NULL;

void ui_create_media_screen() {
    media_screen = lv_obj_create(NULL);
    
    // Container for controls
    lv_obj_t * cont = lv_obj_create(media_screen);
    lv_obj_set_size(cont, lv_pct(90), lv_pct(80));
    lv_obj_center(cont);
    lv_obj_set_flex_flow(cont, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(cont, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

    // Prev Button
    lv_obj_t * btn_prev = lv_button_create(cont);
    lv_obj_set_size(btn_prev, 80, 80);
    lv_obj_t * lbl_prev = lv_label_create(btn_prev);
    lv_label_set_text(lbl_prev, LV_SYMBOL_PREV);
    lv_obj_center(lbl_prev);

    // Play/Pause Button
    lv_obj_t * btn_play = lv_button_create(cont);
    lv_obj_set_size(btn_play, 100, 100);
    lv_obj_t * lbl_play = lv_label_create(btn_play);
    lv_label_set_text(lbl_play, LV_SYMBOL_PLAY);
    lv_obj_center(lbl_play);

    // Next Button
    lv_obj_t * btn_next = lv_button_create(cont);
    lv_obj_set_size(btn_next, 80, 80);
    lv_obj_t * lbl_next = lv_label_create(btn_next);
    lv_label_set_text(lbl_next, LV_SYMBOL_NEXT);
    lv_obj_center(lbl_next);
}

lv_obj_t* ui_get_media_screen() {
    if (!media_screen) {
        ui_create_media_screen();
    }
    return media_screen;
}

/**
 * @file lv_conf.h
 * Configuration file for v9.2.0
 */

#ifndef LV_CONF_H
#define LV_CONF_H

#include <stdint.h>

/*====================
   COLOR SETTINGS
 *====================*/

/*Color depth: 1 (1 byte per pixel), 8 (RGB332), 16 (RGB565), 24 (RGB888), 32 (ARGB8888)*/
#define LV_COLOR_DEPTH 16

/*=========================
   MEMORY SETTINGS
 *=========================*/

/*1: use custom malloc/free, 0: use the built-in `lv_malloc` and `lv_free`*/
#define LV_USE_STDLIB_MALLOC 0

/*Size of the memory available for `lv_malloc` in bytes (>= 2kB)*/
#define LV_MEM_SIZE (128 * 1024U)          /*[bytes]*/

/*=========================
   HAL SETTINGS
 *=========================*/

/*Default display refresh period. LVG will redraw changed areas with this period time*/
#define LV_DEF_REFR_PERIOD 33      /*[ms]*/

/*Input device read period in milliseconds*/
#define LV_DEF_INDEV_READ_PERIOD 33 /*[ms]*/

/*==================
 * FEATURE CONFIGURATION
 *==================*/

/*-------------
 * Drawing
 *-----------*/

/*Enable complex draw engine*/
#define LV_USE_DRAW_SW 1

/*-------------
 * Logging
 *-----------*/

/*Enable the log module*/
#define LV_USE_LOG 1
#define LV_LOG_LEVEL LV_LOG_LEVEL_INFO

/*-------------
 * Others
 *-----------*/

/*1: Enable the runtime performance monitor*/
#define LV_USE_SYSMON 1
#define LV_USE_PERF_MONITOR 1

#endif /*LV_CONF_H*/

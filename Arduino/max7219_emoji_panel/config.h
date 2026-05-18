#pragma once

#include <Arduino.h>

// MAX7219 pins.
// Current working Pro Micro wiring:
//   DIN -> D15
//   CLK -> D16
//   CS  -> D10
// LedControl uses bit-banged output, so these do not have to be hardware SPI pins.
#define PIN_DIN 15
#define PIN_CLK 16
#define PIN_CS  10
#define MATRIX_COUNT 1

// Analog inputs
#define LDR_PIN A0
#define POT_PIN A1

// Measured values for your LDR divider:
// bright: 1000..1015, normal room: 650..850, dark: 220..350
const int LDR_DARK_ADC   = 300;
const int LDR_BRIGHT_ADC = 1010;

// MAX7219 intensity range. 0 is minimum brightness, not complete shutdown.
const uint8_t MIN_INTENSITY = 0;
const uint8_t MAX_INTENSITY = 15;

// Potentiometer limits the maximum display brightness to this range.
const uint8_t USER_MAX_INTENSITY_MIN = 3;
const uint8_t USER_MAX_INTENSITY_MAX = 15;

// Integer EMA smoothing for LDR readings: 8 ~= alpha 0.125.
const uint8_t LDR_EMA_DIV = 8;
const int LDR_EMA_INITIAL = 500;

// Extra ADC margin before switching to a neighboring brightness level.
// This hysteresis reduces visible flicker near threshold values.
const int LDR_HYSTERESIS_ADC = 20;

// Animation timing.
// Each built-in emoji has its own FPS in emojis.h. If an emoji entry has fps=0,
// DEFAULT_ANIM_FPS is used.
const uint8_t MAX_ANIM_FRAMES = 4;
const uint8_t DEFAULT_ANIM_FPS = 8;
const uint8_t MIN_ANIM_FPS = 1;
const uint8_t MAX_ANIM_FPS = 30;
const uint16_t DEFAULT_SHOW_MS = 1600;
const uint16_t IMG_REFRESH_MS = 120;
const uint16_t FADE_STEP_DELAY_MS = 35;

// Serial
const uint32_t SERIAL_BAUD = 115200;
const uint8_t LINE_BUF_SIZE = 128;
const uint8_t MAX_TOKENS = 16;

// Optional diagnostics. Can be toggled with: DEBUG 1 / DEBUG 0
const uint16_t DEBUG_PRINT_PERIOD_MS = 500;

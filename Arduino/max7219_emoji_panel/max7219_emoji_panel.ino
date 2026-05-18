/*
 * MAX7219 8x8 Emoji Panel
 * Board: Arduino Pro Micro / ATmega32U4 clone
 * Display: one MAX7219 8x8 LED matrix module
 *
 * Commands over Serial @115200:
 *   EMO <name> [ms] [fps]   Example: EMO HAPPY 1600
 *                            Example with temporary FPS override: EMO HEART 1600 15
 *   IMG <b0> ... <b7> [ms]  Example: IMG 0x3C 0x42 0xA5 0x81 0xA5 0x99 0x42 0x3C 1600
 *   LIST
 *   CLEAR
 *   DEBUG 1 / DEBUG 0
 *   HELP
 * Replies:
 *   OK ... on accepted commands, ERR: ... on invalid commands.
 *
 * Built-in emojis:
 *   Stored in PROGMEM.
 *   Each emoji can have 1..MAX_ANIM_FRAMES frames and its own FPS.
 *
 * Brightness:
 *   LDR divider on A0.
 *   Potentiometer on A1 limits maximum brightness.
 *   Gamma-like ADC -> intensity curve is implemented as a PROGMEM LUT, no pow()/math.h.
 */

#include <Arduino.h>
#include <LedControl.h>
#include <avr/pgmspace.h>
#include <stdlib.h>
#include "config.h"
#include "emojis.h"

LedControl lc(PIN_DIN, PIN_CLK, PIN_CS, MATRIX_COUNT);

// Gamma-like brightness curve for gamma ~= 2.8, 64 samples, output 0..15.
// This saves Flash compared to pow() and behaves predictably on AVR.
const uint8_t BRIGHTNESS_LUT[64] PROGMEM = {
  0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 1, 1, 1, 1, 1,
  1, 1, 1, 1, 2, 2, 2, 2,
  2, 2, 3, 3, 3, 3, 4, 4,
  4, 5, 5, 5, 5, 6, 6, 7,
  7, 7, 8, 8, 9, 9,10,10,
 11,11,12,12,13,14,14,15
};

char lineBuf[LINE_BUF_SIZE];
uint8_t linePos = 0;

int ldrEMA = LDR_EMA_INITIAL;
int lastRawLdr = 0;
int lastPot = 0;
uint8_t lastBaseIntensity = 0;
uint8_t lastIntensity = 0;
bool baseIntensityInitialized = false;
bool debugEnabled = false;
unsigned long lastDebugPrintMs = 0;

enum DisplayMode {
  DISPLAY_IDLE,
  DISPLAY_ANIM,
  DISPLAY_IMAGE
};

DisplayMode displayMode = DISPLAY_IDLE;
AnimDef activeAnim;
uint8_t activeFrame = 0;
uint8_t activeFrameCount = 1;
uint16_t activeFrameDelayMs = IMG_REFRESH_MS;
uint32_t activeUntilMs = 0;
uint32_t nextFrameMs = 0;
uint8_t activeImage[8];

// -------------------- Small helpers --------------------

bool isSpaceChar(char c)
{
  return c == ' ' || c == '\t';
}

char upperAscii(char c)
{
  if (c >= 'a' && c <= 'z') return c - 32;
  return c;
}

bool equalsIgnoreCase(const char *a, const char *b)
{
  while (*a && *b) {
    if (upperAscii(*a) != upperAscii(*b)) return false;
    a++;
    b++;
  }
  return *a == '\0' && *b == '\0';
}

bool equalsName_P(const char *ramName, PGM_P progmemName)
{
  while (true) {
    char a = upperAscii(*ramName++);
    char b = upperAscii((char)pgm_read_byte(progmemName++));

    if (a != b) return false;
    if (a == '\0') return true;
  }
}

long mapLong(long x, long inMin, long inMax, long outMin, long outMax)
{
  if (inMax == inMin) return outMin;
  return (x - inMin) * (outMax - outMin) / (inMax - inMin) + outMin;
}

void printProgmemString(PGM_P p)
{
  char c;
  while ((c = (char)pgm_read_byte(p++)) != '\0') {
    Serial.write(c);
  }
}

bool parseULong(const char *s, unsigned long &out)
{
  if (s == nullptr || *s == '\0') return false;
  char *endPtr = nullptr;
  unsigned long v = strtoul(s, &endPtr, 0);
  if (endPtr == s || *endPtr != '\0') return false;
  out = v;
  return true;
}

bool parseLong(const char *s, long &out)
{
  if (s == nullptr || *s == '\0') return false;
  char *endPtr = nullptr;
  long v = strtol(s, &endPtr, 0);
  if (endPtr == s || *endPtr != '\0') return false;
  out = v;
  return true;
}

uint8_t clampFps(uint8_t fps)
{
  if (fps == 0) fps = DEFAULT_ANIM_FPS;
  if (fps < MIN_ANIM_FPS) fps = MIN_ANIM_FPS;
  if (fps > MAX_ANIM_FPS) fps = MAX_ANIM_FPS;
  return fps;
}

uint16_t frameDelayFromFps(uint8_t fps)
{
  fps = clampFps(fps);
  return (uint16_t)(1000UL / fps);
}

uint8_t safeFrameCount(uint8_t nFrames)
{
  if (nFrames < 1) return 1;
  if (nFrames > MAX_ANIM_FRAMES) return MAX_ANIM_FRAMES;
  return nFrames;
}

// Splits the current line buffer in place.
uint8_t splitTokens(char *line, char **argv, uint8_t maxTokens)
{
  uint8_t argc = 0;
  char *p = line;

  while (*p != '\0' && argc < maxTokens) {
    while (isSpaceChar(*p)) p++;
    if (*p == '\0') break;

    argv[argc++] = p;

    while (*p != '\0' && !isSpaceChar(*p)) p++;
    if (*p == '\0') break;

    *p = '\0';
    p++;
  }

  return argc;
}

bool readSerialLine()
{
  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    if (c == '\r') continue;

    if (c == '\n') {
      lineBuf[linePos] = '\0';
      linePos = 0;
      return lineBuf[0] != '\0';
    }

    if (linePos < LINE_BUF_SIZE - 1) {
      lineBuf[linePos++] = c;
    } else {
      // Line is too long. Keep the buffer safely terminated.
      lineBuf[LINE_BUF_SIZE - 1] = '\0';
    }
  }

  return false;
}

// -------------------- Brightness --------------------

uint8_t baseIntensityFromAdc(int adc)
{
  if (adc < LDR_DARK_ADC) adc = LDR_DARK_ADC;
  if (adc > LDR_BRIGHT_ADC) adc = LDR_BRIGHT_ADC;

  int idx = (int)mapLong(adc, LDR_DARK_ADC, LDR_BRIGHT_ADC, 0, 63);
  if (idx < 0) idx = 0;
  if (idx > 63) idx = 63;

  return pgm_read_byte(&BRIGHTNESS_LUT[idx]);
}

int adcForLutIndex(int idx)
{
  if (idx < 0) idx = 0;
  if (idx > 63) idx = 63;
  return (int)mapLong(idx, 0, 63, LDR_DARK_ADC, LDR_BRIGHT_ADC);
}

int lowerAdcForIntensity(uint8_t intensity)
{
  for (int idx = 0; idx < 64; idx++) {
    uint8_t level = pgm_read_byte(&BRIGHTNESS_LUT[idx]);
    if (level >= intensity) {
      return adcForLutIndex(idx);
    }
  }

  return LDR_BRIGHT_ADC;
}

int upperAdcForIntensity(uint8_t intensity)
{
  for (int idx = 63; idx >= 0; idx--) {
    uint8_t level = pgm_read_byte(&BRIGHTNESS_LUT[idx]);
    if (level <= intensity) {
      return adcForLutIndex(idx);
    }
  }

  return LDR_DARK_ADC;
}

uint8_t baseIntensityWithHysteresis(int adc, uint8_t targetIntensity)
{
  if (!baseIntensityInitialized) {
    baseIntensityInitialized = true;
    return targetIntensity;
  }

  uint8_t current = lastBaseIntensity;
  if (targetIntensity == current) return current;

  if (targetIntensity > current && current < MAX_INTENSITY) {
    int riseAdc = lowerAdcForIntensity(current + 1) + LDR_HYSTERESIS_ADC;
    if (adc < riseAdc) return current;
  } else if (targetIntensity < current && current > MIN_INTENSITY) {
    int fallAdc = upperAdcForIntensity(current - 1) - LDR_HYSTERESIS_ADC;
    if (adc > fallAdc) return current;
  }

  return targetIntensity;
}

uint8_t applyPotLimit(uint8_t baseIntensity)
{
  lastPot = analogRead(POT_PIN);

  int userMax = (int)mapLong(lastPot, 0, 1023, USER_MAX_INTENSITY_MIN, USER_MAX_INTENSITY_MAX);
  if (userMax < USER_MAX_INTENSITY_MIN) userMax = USER_MAX_INTENSITY_MIN;
  if (userMax > USER_MAX_INTENSITY_MAX) userMax = USER_MAX_INTENSITY_MAX;

  int limited = (int)mapLong(baseIntensity, 0, 15, 0, userMax);
  if (limited < MIN_INTENSITY) limited = MIN_INTENSITY;
  if (limited > MAX_INTENSITY) limited = MAX_INTENSITY;

  return (uint8_t)limited;
}

uint8_t readAutoIntensity()
{
  lastRawLdr = analogRead(LDR_PIN);

  // Integer exponential moving average. No float math on small AVR boards.
  ldrEMA = ((long)ldrEMA * (LDR_EMA_DIV - 1) + lastRawLdr) / LDR_EMA_DIV;

  uint8_t targetBaseIntensity = baseIntensityFromAdc(ldrEMA);
  lastBaseIntensity = baseIntensityWithHysteresis(ldrEMA, targetBaseIntensity);
  lastIntensity = applyPotLimit(lastBaseIntensity);
  return lastIntensity;
}

void applyAutoBrightness()
{
  lc.setIntensity(0, readAutoIntensity());
}

void maybePrintDebug()
{
  if (!debugEnabled) return;

  unsigned long now = millis();
  if (now - lastDebugPrintMs < DEBUG_PRINT_PERIOD_MS) return;
  lastDebugPrintMs = now;

  Serial.print(F("LDR raw="));
  Serial.print(lastRawLdr);
  Serial.print(F(" ema="));
  Serial.print(ldrEMA);
  Serial.print(F(" base="));
  Serial.print(lastBaseIntensity);
  Serial.print(F(" pot="));
  Serial.print(lastPot);
  Serial.print(F(" intensity="));
  Serial.println(lastIntensity);
}

// -------------------- Display --------------------

void drawBitmapRam(const uint8_t *bmp)
{
  for (uint8_t row = 0; row < 8; row++) {
    lc.setRow(0, row, bmp[row]);
  }
}

void drawFrame_P(const uint8_t *frames, uint8_t frameIndex)
{
  const uint8_t *frame = frames + ((uint16_t)frameIndex * 8);

  for (uint8_t row = 0; row < 8; row++) {
    uint8_t v = pgm_read_byte(frame + row);
    lc.setRow(0, row, v);
  }
}

void fadeOutFrom(uint8_t startIntensity)
{
  for (int i = startIntensity; i >= 0; i--) {
    lc.setIntensity(0, i);
    delay(FADE_STEP_DELAY_MS);
  }
  lc.clearDisplay(0);
}

// -------------------- Emoji registry --------------------

int findAnimIndexByName(const char *name)
{
  for (uint8_t i = 0; i < N_ANIMS; i++) {
    AnimDef a;
    memcpy_P(&a, &ANIMS[i], sizeof(a));

    if (equalsName_P(name, a.name)) {
      return i;
    }
  }

  return -1;
}

void printList()
{
  Serial.println(F("Available EMO names:"));

  for (uint8_t i = 0; i < N_ANIMS; i++) {
    AnimDef a;
    memcpy_P(&a, &ANIMS[i], sizeof(a));

    uint8_t frames = safeFrameCount(a.nFrames);
    uint8_t fps = clampFps(a.fps);

    Serial.print(F("  "));
    printProgmemString(a.name);
    Serial.print(F(" frames="));
    Serial.print(frames);
    Serial.print(F(" fps="));
    Serial.println(fps);
  }
}

bool timeReached(uint32_t now, uint32_t target)
{
  return (int32_t)(now - target) >= 0;
}

void stopDisplay(bool clearPanel)
{
  displayMode = DISPLAY_IDLE;
  activeFrame = 0;
  if (clearPanel) {
    lc.clearDisplay(0);
  }
}

void drawActiveFrame()
{
  if (displayMode == DISPLAY_ANIM) {
    drawFrame_P(activeAnim.frames, activeFrame);
    activeFrame++;
    if (activeFrame >= activeFrameCount) activeFrame = 0;
  } else if (displayMode == DISPLAY_IMAGE) {
    drawBitmapRam(activeImage);
  }

  applyAutoBrightness();
  nextFrameMs = millis() + activeFrameDelayMs;
}

void updateDisplay()
{
  if (displayMode == DISPLAY_IDLE) {
    applyAutoBrightness();
    return;
  }

  uint32_t now = millis();
  if (timeReached(now, activeUntilMs)) {
    fadeOutFrom(readAutoIntensity());
    stopDisplay(false);
    return;
  }

  if (timeReached(now, nextFrameMs)) {
    drawActiveFrame();
  } else {
    applyAutoBrightness();
  }
}

void startAnimByIndex(int index, uint32_t showMs, uint8_t fpsOverride)
{
  if (index < 0 || index >= N_ANIMS) return;

  memcpy_P(&activeAnim, &ANIMS[index], sizeof(activeAnim));
  activeFrameCount = safeFrameCount(activeAnim.nFrames);
  uint8_t fps = (fpsOverride == 0) ? activeAnim.fps : fpsOverride;
  activeFrameDelayMs = frameDelayFromFps(fps);
  activeFrame = 0;
  activeUntilMs = millis() + showMs;
  nextFrameMs = 0;
  displayMode = DISPLAY_ANIM;
  drawActiveFrame();
}

void startImage(const uint8_t bmp[8], uint32_t showMs)
{
  for (uint8_t i = 0; i < 8; i++) {
    activeImage[i] = bmp[i];
  }

  activeFrameDelayMs = IMG_REFRESH_MS;
  activeFrame = 0;
  activeFrameCount = 1;
  activeUntilMs = millis() + showMs;
  nextFrameMs = 0;
  displayMode = DISPLAY_IMAGE;
  drawActiveFrame();
}

// -------------------- Commands --------------------

void printHelp()
{
  Serial.println(F("Commands:"));
  Serial.println(F("  EMO <name> [ms] [fps]"));
  Serial.println(F("  IMG <b0> <b1> <b2> <b3> <b4> <b5> <b6> <b7> [ms]"));
  Serial.println(F("  LIST"));
  Serial.println(F("  CLEAR"));
  Serial.println(F("  DEBUG 1"));
  Serial.println(F("Examples:"));
  Serial.println(F("  EMO HAPPY 1600"));
  Serial.println(F("  EMO HEART 1600 15"));
  Serial.println(F("  IMG 0x3C 0x42 0xA5 0x81 0xA5 0x99 0x42 0x3C 1600"));
}

void handleEmoCommand(char **argv, uint8_t argc)
{
  if (argc < 2) {
    Serial.println(F("ERR: EMO needs name. Try LIST."));
    return;
  }

  uint32_t showMs = DEFAULT_SHOW_MS;
  if (argc >= 3) {
    unsigned long parsed = 0;
    if (!parseULong(argv[2], parsed)) {
      Serial.println(F("ERR: bad duration."));
      return;
    }
    showMs = parsed;
  }

  uint8_t fpsOverride = 0;
  if (argc >= 4) {
    unsigned long parsed = 0;
    if (!parseULong(argv[3], parsed)) {
      Serial.println(F("ERR: bad FPS."));
      return;
    }
    if (parsed > 255) parsed = 255;
    fpsOverride = (uint8_t)parsed;
  }

  int index = findAnimIndexByName(argv[1]);
  if (index < 0) {
    Serial.println(F("ERR: unknown EMO name. Try LIST."));
    return;
  }

  Serial.print(F("OK EMO "));
  Serial.print(argv[1]);
  Serial.print(F(" "));
  Serial.println(showMs);
  startAnimByIndex(index, showMs, fpsOverride);
}

void handleImgCommand(char **argv, uint8_t argc)
{
  if (argc < 9) {
    Serial.println(F("ERR: IMG needs 8 row bytes."));
    return;
  }

  uint8_t rows[8];

  for (uint8_t i = 0; i < 8; i++) {
    long v = 0;
    if (!parseLong(argv[i + 1], v)) {
      Serial.println(F("ERR: bad IMG byte."));
      return;
    }
    if (v < 0) v = 0;
    if (v > 255) v = 255;
    rows[i] = (uint8_t)v;
  }

  uint32_t showMs = DEFAULT_SHOW_MS;
  if (argc >= 10) {
    unsigned long parsed = 0;
    if (!parseULong(argv[9], parsed)) {
      Serial.println(F("ERR: bad duration."));
      return;
    }
    showMs = parsed;
  }

  Serial.println(F("OK IMG"));
  startImage(rows, showMs);
}

void handleDebugCommand(char **argv, uint8_t argc)
{
  if (argc < 2) {
    Serial.println(debugEnabled ? F("DEBUG=1") : F("DEBUG=0"));
    return;
  }

  unsigned long v = 0;
  if (!parseULong(argv[1], v)) {
    Serial.println(F("ERR: DEBUG needs 0 or 1."));
    return;
  }

  debugEnabled = (v != 0);
  Serial.println(debugEnabled ? F("DEBUG=1") : F("DEBUG=0"));
}

void handleCommand(char *line)
{
  char *argv[MAX_TOKENS];
  uint8_t argc = splitTokens(line, argv, MAX_TOKENS);
  if (argc == 0) return;

  if (equalsIgnoreCase(argv[0], "EMO")) {
    handleEmoCommand(argv, argc);
  } else if (equalsIgnoreCase(argv[0], "IMG")) {
    handleImgCommand(argv, argc);
  } else if (equalsIgnoreCase(argv[0], "LIST")) {
    printList();
  } else if (equalsIgnoreCase(argv[0], "CLEAR")) {
    stopDisplay(true);
    Serial.println(F("OK CLEAR"));
  } else if (equalsIgnoreCase(argv[0], "DEBUG")) {
    handleDebugCommand(argv, argc);
  } else if (equalsIgnoreCase(argv[0], "HELP") || equalsIgnoreCase(argv[0], "?")) {
    printHelp();
  } else {
    Serial.println(F("ERR: unknown command. Try HELP."));
  }
}

// -------------------- Arduino lifecycle --------------------

void setup()
{
  Serial.begin(SERIAL_BAUD);
  pinMode(LDR_PIN, INPUT);
  pinMode(POT_PIN, INPUT);

  lc.shutdown(0, false);
  lc.setIntensity(0, 8);
  lc.clearDisplay(0);

  Serial.println(F("MAX7219 8x8 Emoji Panel ready."));
  printHelp();
  printList();
}

void loop()
{
  if (readSerialLine()) {
    handleCommand(lineBuf);
  }

  updateDisplay();
  maybePrintDebug();
  delay(2);
}

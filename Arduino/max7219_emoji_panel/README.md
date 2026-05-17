# MAX7219 8x8 Emoji Panel

Firmware for an Arduino-compatible board connected to one MAX7219 8x8 LED
matrix. The Python daemon sends normalized emoji names over Serial, and this
sketch renders the matching built-in animation.

## Components

- Arduino Pro Micro / Leonardo-compatible ATmega32U4 board, 5 V version.
- MAX7219 8x8 LED matrix module.
- LDR photoresistor, for example GL5528.
- 10 kOhm resistor for the LDR divider.
- 10 kOhm potentiometer for user brightness limit.
- Breadboard/jumper wires and a USB data cable.

Other Arduino boards can work too. If you use Uno, Nano, ESP32, or another
pinout, update `PIN_DIN`, `PIN_CLK`, and `PIN_CS` in `config.h`.

## Wiring

The default pinout is for the current Pro Micro build:

| Module | Arduino |
| --- | --- |
| MAX7219 VCC | 5V |
| MAX7219 GND | GND |
| MAX7219 DIN | D15 |
| MAX7219 CLK | D16 |
| MAX7219 CS | D10 |

LDR brightness sensor:

```text
5V --- LDR --- A0 --- 10 kOhm --- GND
```

Potentiometer:

```text
5V  --- outer pin
A1  --- middle pin
GND --- other outer pin
```

The LDR changes automatic brightness. The potentiometer limits the maximum
brightness so the display can be dimmed for a dark room.

## Arduino IDE Setup

1. Install the `LedControl` library from Library Manager.
2. Select a board matching your controller. For many Pro Micro clones, use
   `SparkFun Pro Micro` if SparkFun AVR boards are installed, or `Arduino
   Leonardo` for a compatible ATmega32U4 profile.
3. Open `max7219_emoji_panel.ino`.
4. Check pins and brightness calibration in `config.h`.
5. Upload the sketch.
6. Open Serial Monitor at `115200` baud with line ending `Newline`.

## Serial Protocol

Commands are ASCII lines ending with `\n`:

```text
EMO <name> [ms] [fps]
IMG <b0> <b1> <b2> <b3> <b4> <b5> <b6> <b7> [ms]
LIST
CLEAR
DEBUG 1
DEBUG 0
HELP
```

Examples:

```text
EMO HAPPY 2000
EMO HEART 3000 15
EMO CAT 3000
CLEAR
LIST
IMG 0x3C 0x42 0xA5 0x81 0xA5 0x99 0x42 0x3C 3000
```

Responses used by the Python daemon:

```text
OK EMO CAT 3000
OK CLEAR
ERR: unknown EMO name. Try LIST.
```

`EMO` starts a non-blocking display state. While an animation is active, the
main loop still reads Serial, so a new `EMO` replaces the current one and
`CLEAR` clears the matrix immediately.

## Built-In Names

```text
HAPPY LAUGH WINK SURPRISE SAD CRY ANGRY LOVE KISS COOL SLEEP NEUTRAL
CONFUSED THINK TONGUE DEAD WOW HEART YES NO OK ALERT MUSIC ROBOT GHOST
CAT DOG FOOD STAR
```

Run `LIST` to get the same names with frame counts and FPS values.

## Manual Hardware Test

Close the Arduino IDE Serial Monitor before running the Python test helper.

```bash
python -m pip install pyserial
python Arduino/max7219_emoji_panel/test_all_emojis.py /dev/ttyACM0
```

On Windows:

```powershell
py -m pip install pyserial
py Arduino\max7219_emoji_panel\test_all_emojis.py COM3
```

The helper sends every name returned by `LIST`.

## Adding An Emoji

1. Add a PROGMEM name:

```cpp
const char NAME_MYEMO[] PROGMEM = "MYEMO";
```

2. Add frames. One frame is exactly 8 bytes, one byte per row:

```cpp
const uint8_t EMO_MYEMO[] PROGMEM = {
  // frame 0
  0b00111100, 0b01000010, 0b10100101, 0b10000001,
  0b10100101, 0b10011001, 0b01000010, 0b00111100,

  // frame 1
  0b00111100, 0b01000010, 0b10000001, 0b10000001,
  0b10100101, 0b10011001, 0b01000010, 0b00111100
};
```

3. Register it in `ANIMS`:

```cpp
{ NAME_MYEMO, EMO_MYEMO, 2, 7 },
```

The fields are `{ name, frame_array, frame_count, fps }`.
`frame_count` must be `1..MAX_ANIM_FRAMES`. `fps=0` uses
`DEFAULT_ANIM_FPS`.

4. Add Python normalization rules in
`src/emoji_display/emoji.py`, otherwise the daemon will not route user emoji to
the new display name.

## Tuning

Main settings are in `config.h`:

```cpp
const uint8_t MAX_ANIM_FRAMES = 4;
const uint8_t DEFAULT_ANIM_FPS = 8;
const uint8_t MIN_ANIM_FPS = 1;
const uint8_t MAX_ANIM_FPS = 30;
const uint16_t DEFAULT_SHOW_MS = 3000;
```

If the LDR works backward because your divider is reversed, swap the LDR and
resistor positions or adjust `LDR_DARK_ADC` / `LDR_BRIGHT_ADC`.

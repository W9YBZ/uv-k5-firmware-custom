#!/usr/bin/env python3
"""Exercise the actual keypad-lock filter without radio hardware."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'app/app.c').read_text()
start = source.index('    bool lowBatPopup =')
end = source.index('    if (Key <= KEY_9 || Key == KEY_F)', start)
lock_filter = source[start:end]
prelude = r'''
#include <assert.h>
#include <stdbool.h>
#include "driver/keyboard.h"
enum { FUNCTION_FOREGROUND, FUNCTION_TRANSMIT, FUNCTION_RECEIVE, FUNCTION_MONITOR };
enum { DISPLAY_MAIN, DISPLAY_MENU, ACTION_OPT_KEYLOCK = 9 };
enum { BEEP_1KHZ_60MS_OPTIONAL, BEEP_500HZ_60MS_DOUBLE_BEEP_OPTIONAL };
static struct { bool KEY_LOCK; unsigned KEY_M_LONG_PRESS_ACTION; } gEeprom;
static bool gLowBattery, gLowBatteryConfirmed, gUpdateDisplay;
static unsigned gScreenToDisplay, gCurrentFunction, gKeypadLocked;
static unsigned beep_count;
static bool passed;
static void AUDIO_PlayBeep(unsigned beep) { ++beep_count; }
static void filter_key(KEY_Code_t Key, bool bKeyPressed, bool bKeyHeld) {
    passed = false;
'''
checks = r'''
    passed = true;
}
static void reset(bool locked, unsigned function) {
    gEeprom.KEY_LOCK = locked;
    gEeprom.KEY_M_LONG_PRESS_ACTION = ACTION_OPT_KEYLOCK;
    gCurrentFunction = function;
    gScreenToDisplay = DISPLAY_MAIN;
    gLowBattery = gLowBatteryConfirmed = gUpdateDisplay = false;
    gKeypadLocked = beep_count = 0;
}
int main(void) {
    for (unsigned function = FUNCTION_FOREGROUND; function <= FUNCTION_MONITOR; ++function) {
        if (function == FUNCTION_TRANSMIT) continue;
        for (KEY_Code_t key = KEY_0; key <= KEY_STAR; ++key) {
            for (unsigned event = 0; event < 3; ++event) {
                reset(true, function);
                filter_key(key, event != 1, event == 2);
#ifdef ENABLE_CUSTOM_SIDEFUNCTIONS
                bool unlock = key == KEY_MENU && event == 2;
#else
                bool unlock = false;
#endif
                assert(passed == unlock);
                assert(beep_count == 0);
                assert(gCurrentFunction == function); // filter never alters RX state
                if (!unlock) assert(gKeypadLocked == 4 && gUpdateDisplay);
            }
        }
        reset(true, function);
        filter_key(KEY_F, true, false);
        assert(!passed && beep_count == 0 && gKeypadLocked == 4);
        filter_key(KEY_F, true, true);
        assert(passed); // long-F unlock still reaches its handler
        for (KEY_Code_t key = KEY_PTT; key <= KEY_MIC_PF2; ++key) {
            for (unsigned event = 0; event < 3; ++event) {
                reset(true, function);
                filter_key(key, event != 1, event == 2);
                assert(passed && beep_count == 0 && !gUpdateDisplay && gKeypadLocked == 0);
            }
        }
    }
    // The filter still bypasses TX key handling and normal unlocked operation.
    for (KEY_Code_t key = KEY_0; key < KEY_INVALID; ++key) {
        reset(true, FUNCTION_TRANSMIT);
        filter_key(key, true, false);
        assert(passed && beep_count == 0);
        reset(false, FUNCTION_FOREGROUND);
        filter_key(key, true, false);
        assert(passed && beep_count == 0);
    }
    // Low-battery confirmation and warnings remain when the keypad is unlocked.
    reset(false, FUNCTION_FOREGROUND);
    gLowBattery = true;
    filter_key(KEY_1, true, false);
    assert(!passed && gKeypadLocked == 4);
#ifdef ENABLE_WARNING
    assert(beep_count == 1);
#endif
    reset(true, FUNCTION_FOREGROUND);
    gLowBattery = true;
    filter_key(KEY_EXIT, true, false);
    assert(!passed && gLowBatteryConfirmed && gUpdateDisplay);
#ifdef ENABLE_WARNING
    assert(beep_count == 1);
#endif
    return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    test = Path(tmp) / 'locked_keys.c'
    exe = Path(tmp) / 'locked_keys'
    test.write_text(prelude + lock_filter + checks)
    for custom in (False, True):
        for warning in (False, True):
            command = ['cc', '-std=c11', '-I', str(ROOT)]
            if custom:
                command.append('-DENABLE_CUSTOM_SIDEFUNCTIONS')
            if warning:
                command.append('-DENABLE_WARNING')
            subprocess.run(command + [str(test), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)
print('Locked panel keys silent; lock display, unlock, PTT/mic/side pass-through, RX state, TX bypass and low-battery feedback checks passed.')

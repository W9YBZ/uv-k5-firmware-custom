#!/usr/bin/env python3
"""Exercise the real key-repeat tail, including state changes during a hold."""
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
s = (ROOT / 'app/app.c').read_text()
a = s.index('    const uint16_t repeatDelay =')
z = s.index('void APP_TimeSlice10ms', a)
repeat = s[a:z]
repeat = repeat[:repeat.rfind('}')]
prelude = r'''
#include <assert.h>
#include <stdbool.h>
#include "driver/keyboard.h"
uint16_t gDebounceCounter;
static bool gKeyBeingHeld;
static struct { bool KEY_LOCK; } gEeprom;
static const uint16_t key_repeat_delay_10ms = 40, key_repeat_10ms = 8;
static unsigned events, first_tick;
static bool toggle_lock;
static void ProcessKey(KEY_Code_t key, bool pressed, bool held) {
    assert(pressed && held);
    if (!events) first_tick = gDebounceCounter;
    ++events;
    if (toggle_lock && key == KEY_F) gEeprom.KEY_LOCK = !gEeprom.KEY_LOCK;
}
static void repeat_tick(KEY_Code_t Key) {
'''
checks = r'''
}
static void reset(bool locked) {
    gEeprom.KEY_LOCK = locked;
    gKeyBeingHeld = false;
    events = first_tick = 0;
    toggle_lock = false;
}
static void hold(KEY_Code_t key, unsigned ticks) {
    for (gDebounceCounter = 3; gDebounceCounter <= ticks; ++gDebounceCounter)
        repeat_tick(key);
}
int main(void) {
    reset(true);
    hold(KEY_F, 199);
    assert(events == 0 && gEeprom.KEY_LOCK);
    reset(true);
    toggle_lock = true;
    hold(KEY_F, 300);
    assert(events == 1 && first_tick == 200 && !gEeprom.KEY_LOCK);
    reset(false);
    toggle_lock = true;
    hold(KEY_F, 300);
    assert(events == 1 && first_tick == 40 && gEeprom.KEY_LOCK); // no second toggle at 2s
    for (KEY_Code_t key = KEY_SIDE2; key <= KEY_MIC_PF2; ++key) {
        reset(true);
        hold(key, 300);
        assert(events == 1 && first_tick == 40);
    }
    reset(true);
    hold(KEY_UP, 64);
    assert(events > 1 && first_tick == 40); // direction-key repeat unchanged
    reset(true);
    hold(KEY_PTT, 300);
    assert(events == 0); // PTT remains on its dedicated path
    return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    test = Path(tmp) / 'hold.c'
    exe = Path(tmp) / 'hold'
    test.write_text(prelude + repeat + checks)
    subprocess.run(['cc','-std=c11','-I',str(ROOT),str(test),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print('F unlock requires 2s; original lock/side-key timing, one action per hold, repeat and PTT bypass checks passed.')

#!/usr/bin/env python3
"""Run the actual welcome-screen wait loop against permanently held keys."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'main.c').read_text()
start = source.index('    while (boot_counter_10ms > 0')
brace = source.index('{', start)
depth = 1
end = brace + 1
while depth:
    depth += (source[end] == '{') - (source[end] == '}')
    end += 1
loop = source[start:end]
prelude = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include "driver/keyboard.h"
static volatile uint8_t boot_counter_10ms;
static KEY_Code_t held_key;
static unsigned polls, beeps;
enum { POWER_ON_DISPLAY_MODE_NONE = 0, POWER_ON_DISPLAY_MODE_MESSAGE = 1 };
static struct { unsigned POWER_ON_DISPLAY_MODE; } gEeprom;
KEY_Code_t KEYBOARD_PollPhysical(void) {
    // Simulate interrupt-driven countdown ticks while a key never releases.
    assert(++polls <= 512);
    if (boot_counter_10ms) --boot_counter_10ms;
    return held_key;
}
#define BEEP_880HZ_40MS_OPTIONAL 1
static void AUDIO_PlayBeep(unsigned beep) { ++beeps; }
static void wait_welcome(void) {
'''
checks = r'''
}
int main(void) {
    for (held_key = KEY_0; held_key <= KEY_INVALID; ++held_key) {
        boot_counter_10ms = 250;
        polls = beeps = 0;
        gEeprom.POWER_ON_DISPLAY_MODE = POWER_ON_DISPLAY_MODE_MESSAGE;
        wait_welcome();
        assert(boot_counter_10ms == 0);
        assert(polls == (held_key == KEY_EXIT ? 1 : 250));
    }
#if ENABLE_CHINESE_FULL == 4
    boot_counter_10ms = 250;
    polls = beeps = 0;
    held_key = KEY_1;
    gEeprom.POWER_ON_DISPLAY_MODE = POWER_ON_DISPLAY_MODE_NONE;
    wait_welcome();
    assert(boot_counter_10ms == 0 && polls == 1);
#endif
    return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    test = Path(tmp) / 'boot_wait.c'
    executable = Path(tmp) / 'boot_wait'
    test.write_text(prelude + loop + checks)
    for chinese_full in (0, 4):
        for boot_beeps in (False, True):
            command = ['cc', '-std=c11', '-I', str(ROOT), f'-DENABLE_CHINESE_FULL={chinese_full}']
            if boot_beeps:
                command.append('-DENABLE_BOOT_BEEPS')
            subprocess.run(command + [str(test), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
print('Welcome timeout with every held key, EXIT skip and optional display/beep configurations passed.')

#!/usr/bin/env python3
"""Exercise the firmware's actual mic-PF reader with a simulated ADC."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'driver/keyboard.c').read_text()
def extract_function(signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

reader = extract_function('static KEY_Code_t KEYBOARD_ReadMicPf(void) {')
physical = extract_function('KEY_Code_t KEYBOARD_PollPhysical(void) {')
matrix_start = source.index('static const struct {')
matrix_end = source.index('\n#if defined(ENABLE_MIC_PF)', matrix_start)
matrix = source[matrix_start:matrix_end]
prelude = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include "driver/keyboard.h"
#include "driver/gpio.h"
#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))
static struct { volatile uint32_t DATA; } gpioa = {0xffff};
#define GPIOA (&gpioa)
static KEY_Code_t physical_key = KEY_INVALID;
static void SYSTICK_DelayUs(unsigned delay) {
    gpioa.DATA |= 0x78u;
    if (!(gpioa.DATA & (1u << GPIOA_PIN_KEYBOARD_7))) {
        if (physical_key == KEY_EXIT) gpioa.DATA &= ~(1u << GPIOA_PIN_KEYBOARD_0);
        if (physical_key == KEY_F) gpioa.DATA &= ~(1u << GPIOA_PIN_KEYBOARD_3);
    }
}
#define MIC_PF_ADC_CH 2
#define MIC_PF_ADC_PF1_MAX 1100
#define MIC_PF_ADC_PF2_MIN 1200
#define MIC_PF_ADC_PF2_MAX 2000
#define MIC_PF_ADC_RELEASE_MIN 3300
#define MIC_PF_RELEASE_COUNT 2
#define PORTCON_PORTA_SEL0_A7_MASK 0xF0000000u
#define PORTCON_PORTA_SEL0_A7_BITS_SARADC_CH2 0x20000000u
static uint32_t PORTCON_PORTA_SEL0 = 0x12345678u;
static uint16_t sample;
static bool serial_busy;
static bool adc_ready = true;
static bool SerialConfigInProgress(void) { return serial_busy; }
static unsigned adc_starts;
static void ADC_Start(void) { ++adc_starts; }
static bool ADC_CheckEndOfConversion(unsigned channel) { return adc_ready; }
static uint16_t ADC_GetValue(unsigned channel) { return sample; }
'''
checks = r'''
static KEY_Code_t read_voltage(uint16_t voltage) {
    sample = voltage;
    KEY_Code_t key = KEYBOARD_ReadMicPf();
    assert(PORTCON_PORTA_SEL0 == 0x12345678u);
    return key;
}
int main(void) {
    // Startup polls must never consult the accessory ladder, even if stuck low.
    sample = 500;
    unsigned startup_ticks = 250;
    unsigned iterations = 0;
    while (startup_ticks > 0 || KEYBOARD_PollPhysical() != KEY_INVALID) {
        assert(KEYBOARD_PollPhysical() == KEY_INVALID);
        if (startup_ticks > 0) --startup_ticks;
        assert(++iterations <= 250);
    }
    assert(adc_starts == 0);
    physical_key = KEY_EXIT;
    assert(KEYBOARD_PollPhysical() == KEY_EXIT);
    physical_key = KEY_F;
    assert(KEYBOARD_PollPhysical() == KEY_F);
    physical_key = KEY_INVALID;
    assert(KEYBOARD_PollPhysical() == KEY_INVALID);

    // A different accessory can hold the ladder inside either PF range forever.
    for (unsigned i = 0; i < 100; ++i) {
        assert(read_voltage(500) == KEY_INVALID);
        assert(read_voltage(1700) == KEY_INVALID);
    }
    // One high sample, or an incomplete conversion, must not arm a button.
    assert(read_voltage(3500) == KEY_INVALID);
    assert(read_voltage(500) == KEY_INVALID);
    adc_ready = false;
    assert(read_voltage(3500) == KEY_INVALID);
    adc_ready = true;
    assert(read_voltage(500) == KEY_INVALID);
    // Two consecutive released polls arm normal mic-PF operation.
    assert(read_voltage(3500) == KEY_INVALID);
    assert(read_voltage(3500) == KEY_INVALID);
    assert(read_voltage(500) == KEY_MIC_PF1);
    assert(read_voltage(1700) == KEY_MIC_PF1); // latched until release
    assert(read_voltage(2500) == KEY_MIC_PF1); // dead band is not release
    assert(read_voltage(3500) == KEY_MIC_PF1);
    assert(read_voltage(3500) == KEY_INVALID);
    assert(read_voltage(1700) == KEY_MIC_PF2);
    assert(read_voltage(3500) == KEY_MIC_PF2);
    assert(read_voltage(3500) == KEY_INVALID);
    serial_busy = true;
    assert(read_voltage(500) == KEY_INVALID);
    serial_busy = false;
    assert(read_voltage(500) == KEY_MIC_PF1);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    test = Path(tmp) / 'mic_pf.c'
    executable = Path(tmp) / 'mic_pf'
    test.write_text(prelude + matrix + reader + physical + checks)
    subprocess.run(['cc', '-std=c11', '-I', str(ROOT), str(test), '-o', str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
print('Physical boot polling, EXIT/F keys, mic PF startup, arming, hold/release, UART bypass and PA7 restoration checks passed.')

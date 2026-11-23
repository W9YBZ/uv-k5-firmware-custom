#!/usr/bin/env python3
"""Check actual side-action dispatch and persisted IDs without radio hardware."""
from pathlib import Path
import re
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
action = (ROOT / 'app/action.c').read_text()
settings = (ROOT / 'settings.h').read_text()
audio = (ROOT / 'audio.h').read_text()
def function(text, signature):
    a = text.index(signature)
    z = text.index('{', a) + 1
    depth = 1
    while depth:
        depth += (text[z] == '{') - (text[z] == '}')
        z += 1
    return text[a:z]
def enumeration(text, signature):
    a = text.index(signature)
    return text[a:text.index('};', a) + 2]
select = function(action, 'static BEEP_Type_t ACTION_SelectBeep(')
handle = function(action, 'void ACTION_Handle(')
settings_c = (ROOT / 'settings.c').read_text()
validate = function(settings_c, 'static __attribute__((noinline)) uint8_t SETTINGS_LoadShortAction(')
enums = enumeration(settings, 'enum ACTION_OPT_t {') + enumeration(audio, 'enum BEEP_Type_t')
menu_source = (ROOT / 'ui/menu.c').read_text()
a = menu_source.index('const t_sidefunction SIDEFUNCTIONS[]')
side_menu = menu_source[a:menu_source.index('};', a) + 2]
table_start = action.index('void (*action_opt_table[])(void) = {')
table = action[table_start:action.index('};', table_start) + 2]
names = set(re.findall(r'=\s*&([A-Za-z_]\w*)', table)) - {'FUNCTION_NOP'}
aliases = ''.join(f'#define {name} FUNCTION_NOP\n' for name in sorted(names))
audio_c = (ROOT / 'audio.c').read_text()
a = audio_c.index('    if (Beep !=')
z = audio_c.index('#ifdef ENABLE_FMRADIO', a)
audio_gate = audio_c[a:z]
prelude = r''' 
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include "driver/keyboard.h"
#include "chinese.h"
typedef struct { char *name; uint8_t id; } t_sidefunction;
ENUMS
typedef enum BEEP_Type_t BEEP_Type_t;
static bool ACTION_GetToggleWillEnable(enum ACTION_OPT_t action, bool *value) { return false; }
static struct {
 uint8_t KEY_1_SHORT_PRESS_ACTION, KEY_1_LONG_PRESS_ACTION;
 uint8_t KEY_2_SHORT_PRESS_ACTION, KEY_2_LONG_PRESS_ACTION;
 uint8_t MIC_PF1_SHORT_PRESS_ACTION, MIC_PF1_LONG_PRESS_ACTION;
 uint8_t MIC_PF2_SHORT_PRESS_ACTION, MIC_PF2_LONG_PRESS_ACTION;
 uint8_t KEY_M_LONG_PRESS_ACTION, TX_VFO;
 bool BEEP_CONTROL;
} gEeprom;
enum { DISPLAY_MAIN = 0 };
static unsigned gScreenToDisplay, gRequestDisplayScreen, gDTMF_InputBox_Index;
static bool gDTMF_InputMode, gPttWasReleased, gFlagReconfigureVfos, gFlagStopTX;
static char gDTMF_InputBox[16];
static uint8_t gFlagLastVfo;
static BEEP_Type_t gBeepToPlay;
static unsigned noops, tx_calls;
static void FUNCTION_NOP(void) { ++noops; }
static void GENERIC_Key_PTT(bool pressed) { ++tx_calls; }
enum { FUNCTION_FOREGROUND, FUNCTION_TRANSMIT, FUNCTION_RECEIVE, FUNCTION_MONITOR };
static unsigned gCurrentFunction, audible;
TABLE_ALIASES
ACTUAL_TABLE
static void play_checked(BEEP_Type_t Beep) {
AUDIO_GATE
 ++audible;
}
'''
checks = r'''
_Static_assert(ACTION_OPT_WIDTH == 15, "Existing saved IDs changed");
#ifdef ENABLE_SIDEFUNCTIONS_SEND
_Static_assert(ACTION_OPT_SEND_CURRENT == 16 && ACTION_OPT_SEND_OTHER == 17, "TX IDs changed");
_Static_assert(ACTION_OPT_VOLUME_TEST == 18, "Preview must be appended");
#endif
int main(void) {
 _Static_assert(sizeof(action_opt_table)/sizeof(action_opt_table[0]) == ACTION_OPT_LEN, "Action table size");
 gCurrentFunction = FUNCTION_FOREGROUND;
 gEeprom.BEEP_CONTROL = false;
 play_checked(BEEP_880HZ_200MS);
 assert(audible == 1); // preview is explicit, independent of optional key beeps
 audible = 0;
 play_checked(BEEP_1KHZ_60MS_OPTIONAL);
 assert(audible == 0);
 gCurrentFunction = FUNCTION_RECEIVE;
 play_checked(BEEP_880HZ_200MS);
 assert(audible == 0);
 gCurrentFunction = FUNCTION_MONITOR;
 play_checked(BEEP_880HZ_200MS);
 assert(audible == 0);
 gCurrentFunction = FUNCTION_FOREGROUND;
 unsigned menu_count = sizeof(SIDEFUNCTIONS) / sizeof(SIDEFUNCTIONS[0]);
 unsigned short_count = menu_count;
#ifdef ENABLE_SIDEFUNCTIONS_SEND
 assert(SIDEFUNCTIONS[menu_count-2].id == ACTION_OPT_SEND_CURRENT);
 assert(SIDEFUNCTIONS[menu_count-1].id == ACTION_OPT_SEND_OTHER);
 short_count -= 2;
#endif
 bool preview_listed = false;
 for (unsigned i = 0; i < short_count; ++i) {
   if (SIDEFUNCTIONS[i].id == ACTION_OPT_VOLUME_TEST) preview_listed = true;
   assert(SETTINGS_LoadShortAction(SIDEFUNCTIONS[i].id, 250) == SIDEFUNCTIONS[i].id);
 }
 assert(preview_listed);
 for (unsigned id = 0; id < 256; ++id) {
   bool expected = id < ACTION_OPT_LEN;
#ifdef ENABLE_SIDEFUNCTIONS_SEND
   expected = id < 16 || id == ACTION_OPT_VOLUME_TEST;
#endif
   assert(SETTINGS_LoadShortAction(id, 250) == (expected ? id : 250));
 }
 uint8_t *shorts[] = {&gEeprom.KEY_1_SHORT_PRESS_ACTION, &gEeprom.KEY_2_SHORT_PRESS_ACTION,
                     &gEeprom.MIC_PF1_SHORT_PRESS_ACTION, &gEeprom.MIC_PF2_SHORT_PRESS_ACTION};
 uint8_t *longs[] = {&gEeprom.KEY_1_LONG_PRESS_ACTION, &gEeprom.KEY_2_LONG_PRESS_ACTION,
                    &gEeprom.MIC_PF1_LONG_PRESS_ACTION, &gEeprom.MIC_PF2_LONG_PRESS_ACTION};
 KEY_Code_t keys[] = {KEY_SIDE1, KEY_SIDE2, KEY_MIC_PF1, KEY_MIC_PF2};
 for (unsigned i = 0; i < 4; ++i) {
   *shorts[i] = *longs[i] = ACTION_OPT_VOLUME_TEST;
   gBeepToPlay = BEEP_NONE;
   noops = tx_calls = 0;
   ACTION_Handle(keys[i], true, false);
   assert(gBeepToPlay == BEEP_NONE && noops == 0);
   ACTION_Handle(keys[i], false, false);
   assert(gBeepToPlay == BEEP_880HZ_200MS && noops == 1 && tx_calls == 0);
   assert(!gFlagReconfigureVfos && !gFlagStopTX);
   noops = 0;
   gBeepToPlay = BEEP_NONE;
   ACTION_Handle(keys[i], true, true);
   assert(gBeepToPlay == BEEP_880HZ_200MS && noops == 1);
   gBeepToPlay = BEEP_NONE;
   ACTION_Handle(keys[i], false, true);
   assert(gBeepToPlay == BEEP_NONE && noops == 1 && tx_calls == 0);
 }
 return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    test = Path(tmp) / 'volume.c'
    exe = Path(tmp) / 'volume'
    test.write_text(prelude.replace('ENUMS', enums).replace('TABLE_ALIASES', aliases).replace('ACTUAL_TABLE', table).replace('AUDIO_GATE', audio_gate) + side_menu + validate + select + handle + checks)
    for send in (False, True):
        command = ['cc','-std=c11','-DENABLE_CUSTOM_SIDEFUNCTIONS','-DENABLE_MIC_PF','-DENABLE_BLMIN_TMP_OFF','-DENABLE_ENGLISH','-DENABLE_CHINESE_FULL=0','-I',str(ROOT)]
        if send: command.append('-DENABLE_SIDEFUNCTIONS_SEND')
        subprocess.run(command + [str(test),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)
print('Volume preview: one beep per short/long action, all body/mic keys, stable IDs, valid saved short actions single mandatory beep with key tones off, RX/monitor guard and no TX requests passed.')

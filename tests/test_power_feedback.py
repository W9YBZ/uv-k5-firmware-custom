#!/usr/bin/env python3
"""All three power changes must stay audible with ordinary key tones off."""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
def function(text, signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
def enumeration(text, signature):
    start=text.index(signature);return text[start:text.index('};',start)+2]
action=(ROOT/'app/action.c').read_text()
audio=(ROOT/'audio.c').read_text()
a=audio.index('    if (Beep !=');b=audio.index('#ifdef ENABLE_FMRADIO',a)
gate=audio[a:b]
prelude=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
ENUMS
typedef enum BEEP_Type_t BEEP_Type_t;
enum {OUTPUT_POWER_LOW,OUTPUT_POWER_MID,OUTPUT_POWER_HIGH};
enum {FUNCTION_FOREGROUND,FUNCTION_RECEIVE,FUNCTION_MONITOR,FUNCTION_POWER_SAVE};
enum {BANDWIDTH_WIDE, BANDWIDTH_NARROW};
static struct {uint8_t OUTPUT_POWER,CHANNEL_BANDWIDTH;} vfo, *gTxVfo=&vfo;
static struct {uint8_t TX_VFO;bool KEY_LOCK,BEEP_CONTROL;} gEeprom;
static unsigned gCurrentFunction,gRequestSaveChannel,gRequestDisplayScreen,gScreenToDisplay;
static unsigned audible;
static void play(BEEP_Type_t Beep) {
GATE
 ++audible;
}
'''
mocks=r'''
static bool gRxIdleMode,gEnableSpeaker,unmuted;
static unsigned tone_frequency,tone_calls,sounding_ms;
#define BK4819_REG_71 0x71
static void AUDIO_AudioPathOff(void) {}
static void AUDIO_AudioPathOn(void) {}
static void BK4819_RX_TurnOn(void) {}
static void BK4819_Sleep(void) {}
static uint16_t BK4819_ReadRegister(unsigned reg) { return 0; }
static void BK4819_WriteRegister(unsigned reg, unsigned value) {}
static void BK4819_PlayTone(unsigned frequency, bool local) {tone_frequency=frequency;tone_calls++;}
static void BK4819_ExitTxMute(void) {unmuted=true;}
static void BK4819_EnterTxMute(void) {unmuted=false;}
static void BK4819_TurnsOffTones_TurnsOnRX(void) {}
static void SYSTEM_DelayMs(unsigned ms) {if(unmuted) sounding_ms+=ms;}
'''
checks=r'''
int main(void) {
 for(unsigned enabled=0;enabled<2;enabled++) {
  gEeprom.BEEP_CONTROL=enabled;
  for(unsigned old=OUTPUT_POWER_LOW;old<=OUTPUT_POWER_HIGH;old++) {
   gTxVfo->OUTPUT_POWER=old;gRequestSaveChannel=0;
   BEEP_Type_t beep=ACTION_SelectBeep(ACTION_OPT_POWER);
   ACTION_Power();
   assert(gTxVfo->OUTPUT_POWER==(old+1)%3 && gRequestSaveChannel);
   if(old==OUTPUT_POWER_MID) assert(beep==BEEP_2TONE_RISE_OPTIONAL);
   else if(old==OUTPUT_POWER_HIGH) assert(beep==BEEP_2TONE_FALL_OPTIONAL);
   else assert(beep!=BEEP_2TONE_RISE_OPTIONAL && beep!=BEEP_2TONE_FALL_OPTIONAL);
   for(unsigned state=FUNCTION_FOREGROUND;state<=FUNCTION_MONITOR;state++) {
    gCurrentFunction=state;audible=0;play(beep);
    assert(audible==(state==FUNCTION_FOREGROUND));
   }
  }
  gCurrentFunction=FUNCTION_FOREGROUND;audible=0;play(BEEP_1KHZ_60MS_OPTIONAL);
  assert(audible==enabled); /* Ordinary panel feedback still follows BEEP. */
  gTxVfo->OUTPUT_POWER=OUTPUT_POWER_LOW;
  tone_calls=sounding_ms=0;unmuted=false;
  AUDIO_PlayBeep(ACTION_SelectBeep(ACTION_OPT_POWER));
  assert(tone_calls==1 && tone_frequency==1000 && sounding_ms==60);
  tone_calls=sounding_ms=0;unmuted=false;
  AUDIO_PlayBeep(BEEP_1KHZ_60MS_OPTIONAL);
  assert(tone_calls==enabled && sounding_ms==(enabled?60:0));
 }
}
'''
enums=enumeration((ROOT/'settings.h').read_text(),'enum ACTION_OPT_t {')+enumeration((ROOT/'audio.h').read_text(),'enum BEEP_Type_t')
source=prelude.replace('ENUMS',enums).replace('GATE',gate)
source+='\n'.join(function(action,s) for s in ('static bool ACTION_GetToggleWillEnable(', 'static BEEP_Type_t ACTION_SelectBeep(', 'void ACTION_Power('))+mocks+function(audio,'void AUDIO_PlayBeep(')+checks
with tempfile.TemporaryDirectory() as tmp:
    base=Path(tmp);(base/'power.c').write_text(source)
    subprocess.run(['cc','-std=c11',str(base/'power.c'),'-o',str(base/'power')],check=True)
    subprocess.run([str(base/'power')],check=True)
print('Low/mid/high feedback with key tones on/off, RX/monitor guards and ordinary key-tone policy passed')

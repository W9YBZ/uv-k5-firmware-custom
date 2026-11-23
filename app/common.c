#include <stddef.h>
#include "app/chFrScanner.h"
#include "audio.h"
#include "functions.h"
#include "misc.h"
#include "settings.h"
#include "ui/ui.h"

__attribute__((noinline)) bool COMMON_HasSideKeyLockAction(void) {
#ifdef ENABLE_CUSTOM_SIDEFUNCTIONS
#ifdef ENABLE_MIC_PF
    enum { count = 8 };
    _Static_assert(offsetof(EEPROM_Config_t, MIC_PF2_LONG_PRESS_ACTION) -
                   offsetof(EEPROM_Config_t, KEY_1_SHORT_PRESS_ACTION) == count - 1,
                   "Side-key mappings must remain consecutive bytes");
#else
    enum { count = 4 };
    _Static_assert(offsetof(EEPROM_Config_t, KEY_2_LONG_PRESS_ACTION) -
                   offsetof(EEPROM_Config_t, KEY_1_SHORT_PRESS_ACTION) == count - 1,
                   "Side-key mappings must remain consecutive bytes");
#endif
    // Inspect the byte representation of the four/eight saved side-key actions.
    const unsigned char *actions = (const unsigned char *)&gEeprom;
    for (unsigned i = 0; i < count; ++i)
        if (actions[offsetof(EEPROM_Config_t, KEY_1_SHORT_PRESS_ACTION) + i] == ACTION_OPT_KEYLOCK)
            return true;
#endif
    return false;
}

void COMMON_KeypadLockToggle() {

    if (gScreenToDisplay != DISPLAY_MENU &&
        gCurrentFunction != FUNCTION_TRANSMIT) {    // toggle the keyboad lock

#ifdef ENABLE_VOICE
        gAnotherVoiceID = gEeprom.KEY_LOCK ? VOICE_ID_UNLOCK : VOICE_ID_LOCK;
#endif

        gEeprom.KEY_LOCK = !gEeprom.KEY_LOCK;
        //按键锁定禁止发射 取消
        // RADIO_SetVfoState(VFO_STATE_NORMAL);

        gRequestSaveSettings = true;
    }
}

void COMMON_SwitchVFOs() {
#ifdef ENABLE_SCAN_RANGES
    gScanRangeStart = 0;
#endif
    gEeprom.TX_VFO ^= 1;

    if (gEeprom.CROSS_BAND_RX_TX != CROSS_BAND_OFF)
        gEeprom.CROSS_BAND_RX_TX = gEeprom.TX_VFO + 1;
    if (gEeprom.DUAL_WATCH != DUAL_WATCH_OFF)
        gEeprom.DUAL_WATCH = gEeprom.TX_VFO + 1;

    gRequestSaveSettings = 1;
    gFlagReconfigureVfos = true;
    gScheduleDualWatch = true;

    gRequestDisplayScreen = DISPLAY_MAIN;
}

void COMMON_SwitchVFOMode() {
#ifdef ENABLE_NOAA
    if (gEeprom.VFO_OPEN && !IS_NOAA_CHANNEL(gTxVfo->CHANNEL_SAVE))
#else
    if (gEeprom.VFO_OPEN)
#endif
    {
        if (IS_MR_CHANNEL(gTxVfo->CHANNEL_SAVE)) {    // swap to frequency mode
            gEeprom.ScreenChannel[gEeprom.TX_VFO] = gEeprom.FreqChannel[gEeprom.TX_VFO];
#ifdef ENABLE_VOICE
            gAnotherVoiceID        = VOICE_ID_FREQUENCY_MODE;
#endif
            gRequestSaveVFO = true;
            gVfoConfigureMode = VFO_CONFIGURE_RELOAD;
            return;
        }

        uint8_t Channel = RADIO_FindNextChannel(gEeprom.MrChannel[gEeprom.TX_VFO], 1, false, 0);
        if (Channel != 0xFF) {    // swap to channel mode
            gEeprom.ScreenChannel[gEeprom.TX_VFO] = Channel;
#ifdef ENABLE_VOICE
            AUDIO_SetVoiceID(0, VOICE_ID_CHANNEL_MODE);
            AUDIO_SetDigitVoice(1, Channel + 1);
            gAnotherVoiceID = (VOICE_ID_t)0xFE;
#endif
            gRequestSaveVFO = true;
            gVfoConfigureMode = VFO_CONFIGURE_RELOAD;
            return;
        }
    }
}
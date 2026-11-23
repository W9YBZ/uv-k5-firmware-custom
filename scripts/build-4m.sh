#!/bin/sh
# Chinese firmware plus matching resources for compatible 4Mbit/512KiB EEPROM.
set -eu
case "${1:-all}" in
    all) profiles='spectrum call messaging' ;;
    spectrum|call|messaging) profiles=$1 ;;
    *) echo 'Usage: build-4m.sh [all|spectrum|call|messaging]' >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || exit 2
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0=/src
clean_script_mode=$(stat -c %a del_linux.sh)
trap 'chmod "$clean_script_mode" del_linux.sh' EXIT
mkdir -p artifacts/4m
arm-none-eabi-gcc --version > artifacts/4m/toolchain.txt
for profile in $profiles; do
    spectrum=0; vox=1; message=0
    case "$profile" in
        spectrum) spectrum=1; vox=0; suffix=W9-4M-SPEC-ZH ;;
        call) suffix=W9-4M-CALL-ZH ;;
        messaging) message=1; suffix=W9-4M-MSG-ZH ;;
    esac
    out="artifacts/4m/$profile/zh"
    mkdir -p "$out"
    rm -f "$out/$suffix.bin" "$out/firmware.elf" "$out/firmware.raw.bin" "$out/manifest.json"
    make_profile() {
        make "$@" ENABLE_CHINESE_FULL=4 ENABLE_EEPROM_4M=1 ENABLE_ENGLISH=0 \
            ENABLE_PINYIN=0 ENABLE_DOPPLER=0 ENABLE_4732=0 ENABLE_BOOTLOADER=0 \
            ENABLE_EEPROM_TYPE=0 ENABLE_MIC_PF=1 ENABLE_CUSTOM_SIDEFUNCTIONS=1 \
            ENABLE_SIDEFUNCTIONS_SEND=1 ENABLE_MDC1200=1 ENABLE_MDC1200_EDIT=1 \
            ENABLE_MDC1200_CONTACT=1 ENABLE_MDC1200_SIDE_BEEP=1 ENABLE_FMRADIO=1 \
            ENABLE_SPECTRUM="$spectrum" ENABLE_VOX="$vox" ENABLE_DTMF_CALLING=1 \
            ENABLE_MESSENGER="$message" ENABLE_MESSENGER_DELIVERY_NOTIFICATION="$message" \
            ENABLE_MESSENGER_NOTIFICATION="$message" PACKED_FILE_SUFFIX="$suffix"
    }
    chmod "$clean_script_mode" del_linux.sh
    git rev-parse HEAD > "$out/source-commit.txt"
    if git diff --quiet HEAD; then echo false; else echo true; fi > "$out/source-dirty.txt"
    make_profile -s --eval='print-profile:;@echo $(CFLAGS)' print-profile > "$out/compiler-flags.txt"
    if ! make_profile build > "$out/build.log" 2>&1; then cat "$out/build.log" >&2; exit 1; fi
    cp firmware "$out/firmware.elf"
    cp firmware.bin "$out/firmware.raw.bin"
    cp "$suffix.bin" "$out/$suffix.bin"
    python3 scripts/eeprom-4m-assets.py generate --flags "$out/compiler-flags.txt" --output "$out/eeprom-assets"
    python3 scripts/validate-4m.py "$profile"
done
if [ "${1:-all}" = all ]; then python3 scripts/validate-4m.py; fi

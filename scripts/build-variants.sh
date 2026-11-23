#!/bin/sh
# Run in the toolchain container, from the repository root. Builds are serial.
# Usage: sh scripts/build-variants.sh [all|standard|call|messaging] [all|zh|en]
set -eu
profile_arg=${1:-all}
language_arg=${2:-all}
case "$profile_arg" in
    all) profiles='standard call messaging' ;;
    standard|call|messaging) profiles=$profile_arg ;;
    *) echo 'Unknown profile: choose standard, call, messaging or all' >&2; exit 2 ;;
esac
case "$language_arg" in
    all) languages='zh en' ;;
    zh|en) languages=$language_arg ;;
    *) echo 'Unknown language: choose zh, en or all' >&2; exit 2 ;;
esac
[ "$#" -le 2 ] || { echo 'At most two arguments are supported' >&2; exit 2; }
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0=/src
clean_script_mode=$(stat -c %a del_linux.sh)
trap 'chmod "$clean_script_mode" del_linux.sh' EXIT
mkdir -p artifacts/variants
arm-none-eabi-gcc --version > artifacts/variants/toolchain.txt
for profile in $profiles; do
    for language in $languages; do
        english=0
        upper_language=ZH
        [ "$language" != en ] || { english=1; upper_language=EN; }
        vox=1
        dtmf=1
        message=0
        spectrum=0
        case "$profile" in
            standard)
                spectrum=1
                suffix="W9YBZ_KMC25-PF-$upper_language"
                [ "$language" != zh ] || { vox=0; dtmf=0; }
                ;;
            call) suffix="W9YBZ-CALL-$upper_language" ;;
            messaging)
                message=1
                suffix="W9YBZ-MSG-$upper_language"
                [ "$language" != zh ] || vox=0
                ;;
        esac
        out="artifacts/variants/$profile/$language"
        mkdir -p "$out"
        # Never leave a stale firmware under this profile if the next build fails.
        rm -f "$out/$suffix.bin" "$out/firmware.elf" "$out/firmware.raw.bin" "$out/manifest.json"
        make_profile() {
            make "$@" ENABLE_CHINESE_FULL=0 ENABLE_ENGLISH="$english" \
                ENABLE_EEPROM_TYPE=0 ENABLE_MIC_PF=1 ENABLE_CUSTOM_SIDEFUNCTIONS=1 \
                ENABLE_SIDEFUNCTIONS_SEND=1 ENABLE_MDC1200=1 ENABLE_MDC1200_EDIT=1 \
                ENABLE_MDC1200_CONTACT=1 ENABLE_MDC1200_SIDE_BEEP=1 ENABLE_FMRADIO=1 \
                ENABLE_SPECTRUM="$spectrum" ENABLE_VOX="$vox" ENABLE_DTMF_CALLING="$dtmf" \
                ENABLE_MESSENGER="$message" ENABLE_MESSENGER_DELIVERY_NOTIFICATION="$message" \
                ENABLE_MESSENGER_NOTIFICATION="$message" PACKED_FILE_SUFFIX="$suffix"
        }
        chmod "$clean_script_mode" del_linux.sh
        git rev-parse HEAD > "$out/source-commit.txt"
        if git diff --quiet HEAD; then
            echo false > "$out/source-dirty.txt"
        else
            echo true > "$out/source-dirty.txt"
        fi
        make_profile -s --eval='print-profile:;@echo $(CFLAGS)' print-profile > "$out/compiler-flags.txt"
        if ! make_profile build > "$out/build.log" 2>&1; then
            cat "$out/build.log" >&2
            exit 1
        fi
        cp firmware "$out/firmware.elf"
        cp firmware.bin "$out/firmware.raw.bin"
        cp "$suffix.bin" "$out/$suffix.bin"
        python3 scripts/validate-variants.py "$profile" "$language"
    done
done
if [ "$profile_arg" = all ] && [ "$language_arg" = all ]; then
    python3 scripts/validate-variants.py
fi

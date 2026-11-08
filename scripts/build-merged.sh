#!/bin/sh
# Run inside the toolchain container, from the repository root.
# Chinese profile disables VOX and DTMF calling as requested.
set -eu
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0=/src
mkdir -p artifacts/en artifacts/zh
arm-none-eabi-gcc --version > artifacts/toolchain.txt
make build ENABLE_ENGLISH=1 ENABLE_FMRADIO=1 ENABLE_SPECTRUM=1 ENABLE_MESSENGER=0 ENABLE_MESSENGER_DELIVERY_NOTIFICATION=0 ENABLE_MESSENGER_NOTIFICATION=0 > artifacts/en/build.log 2>&1
cp firmware firmware.bin W9YBZ_KMC25-PF-EN.bin artifacts/en/
zh_options='ENABLE_VOX=0 ENABLE_DTMF_CALLING=0'
zh_output=artifacts/zh
if ! make build ENABLE_ENGLISH=0 ENABLE_FMRADIO=1 ENABLE_SPECTRUM=1 ENABLE_MESSENGER=0 ENABLE_MESSENGER_DELIVERY_NOTIFICATION=0 ENABLE_MESSENGER_NOTIFICATION=0 $zh_options > "$zh_output/build.log" 2>&1; then
    cat "$zh_output/build.log"
    exit 1
fi
cp firmware firmware.bin W9YBZ_KMC25-PF-ZH.bin "$zh_output/"
arm-none-eabi-size artifacts/en/firmware "$zh_output/firmware"

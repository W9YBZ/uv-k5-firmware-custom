#!/bin/sh
# Run inside the toolchain container, from the repository root.
set -eu
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0=/src
mkdir -p artifacts/en artifacts/zh
arm-none-eabi-gcc --version > artifacts/toolchain.txt
cat > artifacts/size-options.mk <<'OPTIONS'
CFLAGS += -fipa-pta -finline-limit=5 -fmerge-all-constants
LDFLAGS += -fipa-pta -finline-limit=5 -fmerge-all-constants
OPTIONS
# Preserve W9YBZ defaults: KMC-25 PF, custom side functions, MDC1200, VOX.
make build ENABLE_ENGLISH=1 ENABLE_FMRADIO=1 ENABLE_SPECTRUM=0 ENABLE_MESSENGER=1 ENABLE_MESSENGER_DELIVERY_NOTIFICATION=1 ENABLE_MESSENGER_NOTIFICATION=1 > artifacts/en/build.log 2>&1
cp firmware firmware.bin W9YBZ_KMC25-PF-EN.bin artifacts/en/
make -f Makefile -f artifacts/size-options.mk build ENABLE_ENGLISH=0 ENABLE_FMRADIO=1 ENABLE_SPECTRUM=0 ENABLE_MESSENGER=1 ENABLE_MESSENGER_DELIVERY_NOTIFICATION=1 ENABLE_MESSENGER_NOTIFICATION=1 > artifacts/zh/build.log 2>&1
cp firmware firmware.bin W9YBZ_KMC25-PF-ZH.bin artifacts/zh/
arm-none-eabi-size artifacts/en/firmware artifacts/zh/firmware

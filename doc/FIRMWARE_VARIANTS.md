# W9YBZ 固件配置 / Firmware profiles

同一套 W9YBZ + losehu 融合源码提供三组中英文构建。源码及更新见 [GitHub 仓库](https://github.com/W9YBZ/uv-k5-firmware-custom)。

## 存储限制

24C512 是 **64KB / 512Kbit EEPROM**，保存设置、信道及校准；不会增加 MCU 的程序 Flash。本固件的程序区仍限制为 **61440 字节（60KiB）**。这些配置全部使用原有低地址 EEPROM 布局，不要求额外字库映像、EEPROM 扩展数据或重新写入信道；可用于已经正确安装并写入原机设置/校准的 24C512。

仓库现成的完整 GB2312 字库范围超过 64KB EEPROM，不能直接把 `ENABLE_CHINESE_FULL=4` 的 K/H 版刷到 24C512。本页六种配置通过取舍频谱等程序功能提供不同版本。另有 4Mbit/512KB EEPROM 的[扩容中文配置及字库准备说明](FIRMWARE_4M.md)，需要配套资源，不适用于 24C512。

## 功能对照

所有版本保留手咪 PF、自定义侧键、Talk Permit、MDC1200（联系人/编辑/本地监听音量）、FM、开机完成单声提示、普通按键不阻塞开机、锁定按键静音、F 两秒/侧键优先解锁，以及 `VOL` 音量试听。

| 配置 | 语言 | VOX | DTMF 呼叫 | 频谱 | 短信/APRS | 程序字节 | 剩余 Flash |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| standard 标准 | 中文 | 关 | 关 | 开 | 关 | 59908 | 1532 |
| standard 标准 | English | 开 | 开 | 开 | 关 | 61440 | 0 |
| call 通话 | 中文 | 开 | 开 | 关 | 关 | 58052 | 3388 |
| call 通话 | English | 开 | 开 | 关 | 关 | 55560 | 5880 |
| messaging 短信 | 中文 | 关 | 开 | 关 | 开 | 60784 | 656 |
| messaging 短信 | English | 开 | 开 | 关 | 开 | 59304 | 2136 |

- **标准版**：与此前 `scripts/build-merged.sh` 的中英文产物逐字节相同，适合保留当前功能组合。
- **通话版**：中文恢复 VOX 和 DTMF 呼叫，以关闭频谱腾出空间；英文也提供相同的通话功能组合，保留更大 Flash 余量。
- **短信版**：恢复短信、APRS 发射及通知，同时保留 DTMF 呼叫。关闭频谱；中文版因空间限制仍关闭 VOX，英文保留 VOX。
- 本表中的 DTMF 呼叫与 MDC1200 是两项功能；所有版本都保留 MDC1200。

## 文件与使用

构建输出到 `artifacts/variants/<profile>/<language>/`：

| 配置 | 中文已打包刷机文件 | 英文已打包刷机文件 |
| --- | --- | --- |
| standard | `W9YBZ_KMC25-PF-ZH.bin` | `W9YBZ_KMC25-PF-EN.bin` |
| call | `W9YBZ-CALL-ZH.bin` | `W9YBZ-CALL-EN.bin` |
| messaging | `W9YBZ-MSG-ZH.bin` | `W9YBZ-MSG-EN.bin` |

选择一份对应语言、功能组合的已打包固件刷入；不是把六份文件同时写入电台。Call/MSG 版本的开机版本文字也带有 CALL/MSG，便于区分。`firmware.raw.bin` 和 `firmware.elf` 仅用于调试及校验，不是已打包刷机文件。

短信版在主界面按 `F+M` 进入短信；MENU 新建、UP 历史、DOWN 编辑 APRS。APRS 编辑器预填示例呼号及坐标，发送前请改为自己的呼号和实际坐标。收发消息及 APRS 需要上机验证；不因更大的 EEPROM 而增加本版未实现的定位或接收功能。

所有配置保留同一套侧键动作编号和设置地址。切换后原侧键分配不会自动替换；功能被编译关闭时，其动作可能不可用。开启 VOX/DTMF 的版本需要在菜单中设置相应参数。已有 EEPROM 备份仍可保留作恢复用途。

## 复现构建

在仓库根目录使用原 GCC 15.2.0 工具链，串行构建：

```sh
docker build -t uvk5-toolchain:alpine3.23 -f scripts/Dockerfile.toolchain scripts
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/src" uvk5-toolchain:alpine3.23 sh scripts/build-variants.sh
```

只构建特定版本，可在命令末尾加参数，例如 `sh scripts/build-variants.sh messaging zh`。配置为 `standard`、`call`、`messaging` 或 `all`；语言为 `zh`、`en` 或 `all`。不同配置不能在同一源码目录并行编译。

完整构建后生成 `artifacts/variants/W9YBZ-firmware-variants.zip`，仅包含六份已打包固件、说明、清单和 SHA256，不混入未打包镜像。单个配置目录另有构建日志、实际编译宏、ELF、原始镜像和 `manifest.json`；总清单为 `manifest.json`、`SHA256SUMS.txt`。

## 验证范围

六个版本均通过编译、60KiB 程序区限制、CRC-XMODEM、解包一致性、ELF 与原始镜像一致性、启动向量检查及实际编译开关核对；同时核对 W9YBZ 菜单、短信入口和频谱数据是否按配置保留。标准版与之前二进制比对相同。相关启动、键盘、解锁、侧键音量试听模拟回归测试通过。新增通话/短信配置尚未上机验证。

## English summary

24C512 provides 64KiB of data EEPROM, not more executable Flash. All six profiles retain the existing EEPROM layout, FM, MDC1200, mic PF, Talk Permit, ready beep, startup-key fixes, silent locked-panel feedback, conditional two-second F unlock and the VOL preview action. No EEPROM font image is required.

Standard preserves the current profiles and produces byte-identical firmware. Call enables VOX and DTMF calling in both languages, with spectrum disabled. Messaging enables messaging/APRS and DTMF calling, with spectrum disabled; Chinese leaves VOX disabled while English retains it. Pick one packed firmware matching your language and desired features. Configure the APRS callsign and coordinates before transmitting. New profiles passed build and binary validation but have not been tested on hardware.

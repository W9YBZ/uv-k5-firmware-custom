# W9YBZ 4Mbit EEPROM 中文配置

本配置针对 **4Mbit = 512KiB（524288 字节）EEPROM**，不是 24C512 的 64KiB。原有[六种中英文固件](FIRMWARE_VARIANTS.md)继续保留，4M 电台也可以使用它们，不需要额外字库。

4M EEPROM 增加的是数据存储。MCU 程序区仍只有 61440 字节，不能因此同时打开全部功能。本配置将中文字库等数据放到 EEPROM，提供以下三个独立中文版本：

| 配置 | 文件 | VOX | DTMF 呼叫 | 频谱 | 短信/APRS | 程序字节 | 剩余 Flash |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| spectrum | `W9-4M-SPEC-ZH.bin` | 关 | 开 | 开 | 关 | 60572 | 868 |
| call | `W9-4M-CALL-ZH.bin` | 开 | 开 | 关 | 关 | 55752 | 5688 |
| messaging | `W9-4M-MSG-ZH.bin` | 开 | 开 | 关 | 开 | 59156 | 2284 |

全部保留手咪 PF、自定义侧键、Talk Permit、MDC1200 联系人/编辑/本地监听音量、FM，以及此前开机、锁定静音、侧键优先解锁和 VOL 音量试听功能。扩容中文字库支持 GB2312 中文信道名及已有的中文开机文字/图片路径；本构建未开启拼音输入、多普勒、SI4732 或自定义引导。短信/APRS 的使用见[配置文档](FIRMWARE_VARIANTS.md)。

英文继续使用原有 standard/call/messaging 英文固件；这些英文配置也适用于 4M EEPROM，无需本页字库补丁。

## 字库未知时的准备顺序

这些是离线编译及校验通过的构建，尚未在本机电台验证。**4M 中文固件依赖本包资源，字库未知时不要只刷固件。** 原 losehu K/H 字库即使存在，也不等于匹配本版新增菜单。需先确认实际 EEPROM 型号及写入工具支持完整 512KiB 和高地址；当前驱动使用 I²C 控制字节的分区位加 16 位字地址，不以容量相同推定所有芯片兼容。

1. 用支持该电台/芯片的工具读取并保存**本机完整 524288 字节 EEPROM 备份**，另存一份原始备份。普通 8KiB 或 64KiB 写频备份不够。本仓库脚本只处理文件，不读取电台。
2. 解压 `W9YBZ-4M-Chinese.zip`，选择一个配置，将它的资源合并到自己的备份中，例如 spectrum：

   ```sh
   python3 eeprom-4m-assets.py apply \
     --backup /path/to/my-radio-512KiB.bin \
     --assets spectrum/zh/eeprom-assets \
     --output /path/to/my-radio-spectrum-512KiB.bin
   ```

   在源码目录操作时，脚本路径为 `scripts/eeprom-4m-assets.py`，资源路径为 `artifacts/4m/spectrum/zh/eeprom-assets`。输出必须是不存在的新文件；脚本不覆盖原始备份，并校验资源长度、范围和 SHA256。
3. 使用兼容的工具写入合并后的 EEPROM 数据并读回比对，再刷**同一配置目录**下已打包的固件。具体写入方法取决于 EEPROM 型号、引导程序和工具；本包不提供自动写入电台的命令。
4. 验证中文菜单/中文信道名、FM、CTCSS/DCS 收发、MDC、手咪 PF 和所选版本功能。切换三种 4M 中文配置时，也要更新该配置的 `menu-names.bin`；其菜单数量/顺序可能不同。

不能将另一台电台的完整 EEPROM 数据当作字库直接写入。没有本机完整备份时，本工具不会生成可写入的整片映像。

## 修改范围

资源从仓库的简体字模、ASCII 字模、CTCSS/DCS 常量和实际启用的菜单表生成，不下载未知整片 EEPROM 文件。

| 地址 | 资源 | 字节数 |
| --- | --- | ---: |
| `0x02480` | 大数字、3×5、小 ASCII 字体 | 1072 |
| `0x02C00` | 50 个 CTCSS、104 个 DCS 常量，小端序 | 308 |
| `0x02E00` | 6763 个 GB2312 简体字，11×12 位打包 | 111590 |
| `0x7F000` | 当前配置菜单名称，每项 14 字节 | 随配置生成，最多 1792 |

合并脚本逐字节检查：**这些范围以外的所有字节不变**。`0x0000–0x1FFF` 原设置/频道/校准区域、`0x2000` 起的开机文字和 `0x2080` 起的图片均保留原备份内容；脚本也不会自动初始化这些内容。若电台原先有其他固件占用上述资源范围，写入会替换这些范围内的数据，原始备份用于恢复。

4M 菜单名称单独放在 `0x7F000`，避免旧版 `0x28B0` 菜单区因新增菜单过多而覆盖亚音表。菜单读取缓冲区的终止符越界也已修复。字模生成过程检查全部字的编码顺序及位打包往返结果。

## 复现

```sh
docker build -t uvk5-toolchain:alpine3.23 -f scripts/Dockerfile.toolchain scripts
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/src" \
  uvk5-toolchain:alpine3.23 sh scripts/build-4m.sh
```

也可在命令末尾追加 `spectrum`、`call` 或 `messaging` 单独构建。所有构建串行执行。输出 `artifacts/4m/<profile>/zh/`，整包为 `artifacts/4m/W9YBZ-4M-Chinese.zip`；包含已打包固件、匹配资源、合并工具、说明和 SHA256。ELF/raw 只用于校验，不用于常规刷机。

## English

These three Chinese builds require compatible 4Mbit/512KiB EEPROM and their matching external resources. The MCU flash limit remains 60KiB. Existing bilingual profiles remain available unchanged; their English builds also work on expanded EEPROM without these resources.

Read and keep your own complete 524288-byte EEPROM backup first. Run the offline `apply` command above with the resources for the selected profile. It verifies hashes, writes a new file, and preserves every byte outside the four documented resource ranges, including existing settings/calibration and welcome data. No device is accessed. Use a tool compatible with the actual chip to write and read back the result, then flash the corresponding packed firmware. The menu bank is profile-specific. These builds have passed offline checks and still need radio validation.

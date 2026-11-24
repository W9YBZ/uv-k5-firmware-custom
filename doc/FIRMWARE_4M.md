# W9YBZ 4Mbit EEPROM 中文配置

本配置针对 **4Mbit = 512KiB（524288 字节）EEPROM**，不是 24C512 的 64KiB。原有[六种中英文固件](FIRMWARE_VARIANTS.md)继续保留，4M 电台也可以使用它们，不需要额外字库。

4M EEPROM 增加的是数据存储。MCU 程序区仍只有 61440 字节，不能因此同时打开全部功能。本配置将中文字库等数据放到 EEPROM，提供以下三个独立中文版本：

| 配置 | 文件 | VOX | DTMF 呼叫 | 频谱 | 短信/APRS | 程序字节 | 剩余 Flash |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| spectrum | `W9-4M-SPEC-ZH.bin` | 关 | 开 | 开 | 关 | 60596 | 844 |
| call | `W9-4M-CALL-ZH.bin` | 开 | 开 | 关 | 关 | 55776 | 5664 |
| messaging | `W9-4M-MSG-ZH.bin` | 开 | 开 | 关 | 开 | 59180 | 2260 |

全部保留手咪 PF、自定义侧键、Talk Permit、MDC1200 联系人/编辑/本地监听音量、FM，以及此前开机、锁定静音、侧键优先解锁和 VOL 音量试听功能。扩容中文字库支持 GB2312 中文信道名及已有的中文开机文字/图片路径；本构建未开启拼音输入、多普勒、SI4732 或自定义引导。短信/APRS 的使用见[配置文档](FIRMWARE_VARIANTS.md)。

英文继续使用原有 standard/call/messaging 英文固件；这些英文配置也适用于 4M EEPROM，无需本页字库补丁。

## 左侧信道编号乱码修复

4M 版读取最长 16 字节信道名，而屏幕右侧宽度有限。旧绘制函数未限制右边界，较长的信道名可能跨入下一显示页左侧，覆盖 `M19`、`M24` 等编号；右侧名称和频率仍可能看起来正常。现按可用宽度绘制完整字符，超出的字符不显示，保留左侧编号。修复覆盖“信道名”和“信道名＋频率”、上下 VFO 及中英文混合名称。

已安装过本包匹配字库的电台，只需刷入同配置的新固件；字库、菜单资源及 EEPROM 布局均未变化，无需重新写字库或恢复整片 EEPROM。该修复只编入扩容中文路径，原标准中英文配置保持原有编译路径。

## 字库写入：使用配套串口工具

K5Web 当前按固件名称匹配协议，未识别本分支的 `W9-4M-…` 名称，因此其字库页可能提示“固件版本不匹配”。即使绕过版本识别，网页的自动字库也没有本版 `0x7F000` 菜单资源。不要靠改名冒充 losehu K/H 来直接写入网页字库。

依据：[K5Web 版本识别代码](https://k5.vicicode.com/assets/default-layout.2fa33053.js)、[字库页写入代码](https://k5.vicicode.com/assets/index.eb10a14f.js)。这是对当前已部署代码的检查，网站后续可能变化。

本包新增 `radio-4m.py`，直接使用本仓库固件已有的串口命令，不需要网页识别固件名称。工具仅适用于本包三种 W9-4M 固件及已确认兼容的 512KiB EEPROM，当前仍只有离线协议模拟测试，尚未上机验证。原驱动使用 I²C 控制字节分区位加 16 位字地址，不以容量相同推定所有芯片兼容。

### 连接和依赖

电台正常开机、退出发射/扫描/FM，插好写频线，关闭 K5Web、CHIRP 等占用串口的软件。此工具使用正常开机串口模式，**不是按住 PTT 的固件升级模式**。有字库之前，4M 中文菜单可能显示异常，但串口资源安装不需要使用中文菜单。

解压最新 `W9YBZ-4M-Chinese.zip`，在解压目录运行。需要 Python 3 和 pyserial：

```sh
python -m pip install pyserial
python radio-4m.py --port COM3 info
```

`COM3` 换成写频线实际端口。Linux 可用 `/dev/ttyUSB0`，命令中的 `python` 可换成 `python3`；若系统限制全局 pip，先建立并激活虚拟环境。串口无权限时需使用具有该串口访问权限的账户。`info` 只进行握手并显示固件版本，不写入 EEPROM。

### 仍在使用原标准固件时

标准版 `ENABLE_CHINESE_FULL=0` 没有扩容串口命令，无法用它读取完整 512KiB。**先保存原有 8KiB 设置/频道/校准备份**：

```sh
python radio-4m.py --port COM3 backup --size 8192 --output original-settings-8KiB.bin
```

备份经过两次读取比对；保留此文件及此前可用的固件。然后通过原有固件升级方式刷入所选 **4M 固件**，正常重新开机，再执行下面的安装命令。若已刷本包 4M 固件，可直接进入下一步。

这是对早期文档“先写字库再刷固件”顺序的修正：工具需要电台先运行支持扩容串口命令的固件。刷 MCU 固件和写 EEPROM 字库是不同步骤。

### 安装所选版本的资源

例如已刷 `W9-4M-SPEC-ZH.bin`（频谱版）：

```sh
python radio-4m.py --port COM3 install --assets spectrum/zh/eeprom-assets --backup my-radio-before-font-512KiB.bin
```

通话版使用 `call/zh/eeprom-assets`，短信版使用 `messaging/zh/eeprom-assets`。工具检查资源清单与电台报告的固件版本必须一致。

安装过程：

1. 读取完整 524288 字节 EEPROM，再读一次核对；保存本机备份及 SHA256 后才开始写入。备份路径必须是不存在的新文件。
2. 仅写入下表四类资源中需要更新的字节，不写整片 EEPROM；每块写完立即读回核对。
3. 再读取完整 EEPROM，核对资源全部正确、资源以外的每个字节均与备份相同。出现 `PASS` 后关机重开，检查中文菜单、FM、CTCSS/DCS、MDC、手咪 PF 等。

全片备份和校验可能需要数分钟，保持连接与供电，不操作电台。超时、读回不一致或版本不符会停止，不自动重试或清空 EEPROM；保留备份及 `.partial` 文件。若安装中断，排除问题后可用新的备份文件名重新安装，已正确写入的块会跳过。

如果只想备份完整 EEPROM，不安装资源：

```sh
python radio-4m.py --port COM3 backup --output my-radio-512KiB.bin
```

源码目录使用时，脚本位于 `scripts/radio-4m.py`，资源路径以 `artifacts/4m/` 为前缀。打包目录下两个 Python 文件必须放在一起。本工具不提供任意地址写入、整片恢复或另一台电台数据导入功能。

### 已有完整备份时的离线合并

原 `eeprom-4m-assets.py apply` 仍可用于离线生成合并文件：

```sh
python eeprom-4m-assets.py apply --backup my-radio-512KiB.bin --assets spectrum/zh/eeprom-assets --output my-radio-patched-512KiB.bin
```

它只处理文件，不访问电台；8KiB/64KiB 备份不能代替 512KiB 完整备份。常规安装优先使用上面的串口 `install`，只写资源范围，不需要恢复整片映像。

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

These Chinese builds require matching external resources and compatible 4Mbit/512KiB EEPROM. K5Web currently does not recognize the W9-4M version names, and its stock font package lacks this fork's menu bank.

Use the bundled `radio-4m.py` in normal powered-on mode (38400 baud), with Python 3 and pyserial. Close other serial clients. Replace COM3 with your actual serial port. On a standard build, first run `backup --size 8192` to preserve settings/calibration, then flash the chosen 4M firmware and restart normally. The expanded serial commands require the 4M build; initial font display may be incorrect until installation.

Run the `install` example above with the matching profile resources and a NEW backup filename. Before writing, it reads the full EEPROM twice and saves your own 524288-byte backup plus SHA256. It writes only changed resource chunks, reads each back, and verifies the entire EEPROM against the expected merged image. All bytes outside resource ranges must match the backup. It stops on errors without retrying or erasing. After PASS, power-cycle the radio. These tools have passed offline protocol tests and still require hardware validation.

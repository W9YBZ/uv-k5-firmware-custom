# W9YBZ 当前固件总览

整理日期：2026-11-24。共 **9 份固件：6 份通用中英文版 + 3 份 4M 扩容中文版**。所有固件来自同一源码提交 `bf9dfae`，包含本轮中功率提示音修复；4M 中文版同时包含左侧 M19/M24 编号乱码修复。各固件对应的完整提交、编译参数、大小和 SHA256 见包内清单。

## 怎么选

- **你目前使用的版本**：4M 中文短信版，文件 `W9-4M-MSG-ZH.bin`，目录 `4m/messaging/zh/`。需要短信/APRS，就继续使用这版。
- **24C512（64KB / 512Kbit）或原机 EEPROM**：选择 `universal/` 下的版本，不需要额外字库。
- **4Mbit（512KB）EEPROM，想要中文信道名**：选择 `4m/` 下的中文版本，首次使用需要匹配的字库资源；4M 电台也可以使用通用版本。
- **要频谱**：通用标准版，或 4M 中文频谱版。
- **要 VOX + DTMF**：通用通话版；4M 用户可用中文通话版或短信版。
- **要英文**：选择通用英文版，共三种；4M EEPROM 也适用，不需要另写字库。

4M EEPROM 增加数据容量，不增加 MCU 程序容量。所有固件程序区仍限制为 **61440 字节**，因此没有同时打开频谱、VOX、短信/APRS 等全部功能的版本。

## 九种固件对照

所有版本均保留 FM、MDC1200、手咪 PF、Talk Permit 和自定义侧键。

| 类别 | 配置 / 语言 | VOX | DTMF 呼叫 | 频谱 | 短信/APRS | 额外字库 | 文件 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 通用 | 标准 / 中文 | 关 | 关 | 开 | 关 | 不需要 | [W9YBZ_KMC25-PF-ZH.bin](universal/standard/zh/W9YBZ_KMC25-PF-ZH.bin) |
| 通用 | Standard / English | 开 | 开 | 开 | 关 | 不需要 | [W9YBZ_KMC25-PF-EN.bin](universal/standard/en/W9YBZ_KMC25-PF-EN.bin) |
| 通用 | 通话 / 中文 | 开 | 开 | 关 | 关 | 不需要 | [W9YBZ-CALL-ZH.bin](universal/call/zh/W9YBZ-CALL-ZH.bin) |
| 通用 | Call / English | 开 | 开 | 关 | 关 | 不需要 | [W9YBZ-CALL-EN.bin](universal/call/en/W9YBZ-CALL-EN.bin) |
| 通用 | 短信 / 中文 | 关 | 开 | 关 | 开 | 不需要 | [W9YBZ-MSG-ZH.bin](universal/messaging/zh/W9YBZ-MSG-ZH.bin) |
| 通用 | Messaging / English | 开 | 开 | 关 | 开 | 不需要 | [W9YBZ-MSG-EN.bin](universal/messaging/en/W9YBZ-MSG-EN.bin) |
| 4M | 频谱 / 中文 | 关 | 开 | 开 | 关 | 需要匹配资源 | [W9-4M-SPEC-ZH.bin](4m/spectrum/zh/W9-4M-SPEC-ZH.bin) |
| 4M | 通话 / 中文 | 开 | 开 | 关 | 关 | 需要匹配资源 | [W9-4M-CALL-ZH.bin](4m/call/zh/W9-4M-CALL-ZH.bin) |
| 4M | 短信 / 中文 | 开 | 开 | 关 | 开 | 需要匹配资源 | [W9-4M-MSG-ZH.bin](4m/messaging/zh/W9-4M-MSG-ZH.bin) |

上述相对文件链接用于解压后的总包；源码仓库内的原始构建位置为 `artifacts/variants/` 和 `artifacts/4m/`。原有历史产物保留，不纳入当前总包。总包不混入 ELF、raw 固件或历史测试版本。

## 共同功能及修复

- 手咪 PF1/PF2、机身侧键短按/长按分配、Talk Permit 起发音。
- MDC1200 编辑、联系人和本地监听音量；需在 MDCMON 及首尾音菜单中正确启用。
- FM、开机完成后单声提示、普通按键按住不阻塞开机。
- 键盘锁定时面板拒绝提示静音，PTT 和侧键仍按既有逻辑处理。
- 未配置侧键锁定动作时，长按 F 约两秒解锁；配置后只用对应侧键解锁。
- `VOL` 侧键音量试听：旋钮调节后手动触发一声试听，不自动检测旋钮。
- 切换功率：高档上升双音、低档下降双音、中档 1000Hz / 60ms 单声；三档均不受普通按键音开关影响，接收/监听时不插入提示音。
- 4M 中文长信道名限制在屏幕右侧，超长部分截断，避免覆盖左侧 M19/M24 等编号。

## 升级及字库

**已安装过匹配资源的当前 4M 用户**：本轮编号显示和中功率提示音修复都没有改变字库或 EEPROM 布局，只刷相同配置的新固件即可，无需重新写字库。

**首次使用 4M 中文版**：参见 `4m/README.md` 或 [详细说明](docs/FIRMWARE_4M.md)。Windows 操作示例：电台正常开机，关闭占用串口的软件，在总包的 `4m` 文件夹打开终端，安装 pyserial 后执行：

```powershell
py -m pip install pyserial
py radio-4m.py --port COM5 info
py radio-4m.py --port COM5 install --assets messaging/zh/eeprom-assets --backup before-font-512KiB.bin
```

`COM5` 换成自己的串口；该例仅适用于已运行 `W9-4M-MSG-ZH` 的电台。频谱版换成 `spectrum`，通话版换成 `call`。工具先备份完整 EEPROM 并重复读取核对，再仅写资源并读回校验，最终出现 `PASS` 后重启。若当前仍是通用版，需先做 8KB 设置/校准备份，再刷支持扩容串口的 4M 固件；完整顺序见详细说明。

切换 4M 功能配置时，应使用该配置对应的菜单资源。不要把另一台电台的完整 EEPROM 数据写入自己的电台。短信/APRS 使用前设置自己的呼号和实际位置，相关操作见 [通用配置说明](docs/FIRMWARE_VARIANTS.md)。

## 清单和验证

`manifest.json` 汇总九份固件，`SHA256SUMS.txt` 校验总包内文件，每个固件目录还包含独立清单和实际编译参数。所有配置已通过编译、Flash 限制、CRC、解包/ELF 一致性和配置检查；相关按键、音频和绘制修复经过离线回归测试。尚未获得这些最新固件在真实电台上的验证结果。

当前通用英文标准版恰好占满 61440 字节；这属于构建限制信息，不改变刷入步骤。

源码仓库中可运行 `python3 scripts/package-catalog.py` 从已验证产物生成总包；默认目录已存在时用 `--output` 指定新目录。九份固件必须来自相同源码提交，文件哈希必须与构建清单一致。

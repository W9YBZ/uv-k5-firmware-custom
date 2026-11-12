# W9YBZ + losehu 融合记录

本次为真实 Git 合并：W9YBZ `9c42b09`（18 个独有提交）与 losehu `49222a9`（7 个独有提交），共同祖先的两侧历史均保留。

保留 W9YBZ 的 Talk Permit TX 启动流程、KMC-25 ADC PF 按键及菜单、MDC1200 本地监听音量、切换提示音、全高信道名。
合入 losehu 的短信/APRS、消息历史与编辑交互、菜单边界、静噪溢出修复及寄存器批量写入优化。

冲突处理：中文 README 合并说明；菜单计数统一使用 UI_MENU_GetMenuCount，保留 TPTone、MDCMON、MPF 菜单项；去除重复的 MENU_GetListCount。
语义冲突处理：MIC_PF=1 时不再自动关闭自定义侧键，否则手咪 PF 菜单及 EEPROM 设置会被裁掉。
附带修复：发送模式枚举从 0 开始，避免原上游值超过 uint8_t 导致 APRS 分支及服务回执判断失效。
中英文输出分别命名 W9YBZ_KMC25-PF-ZH.bin 和 W9YBZ_KMC25-PF-EN.bin，避免互相覆盖。

## 当前可用固件配置

用户最终选择：保留 W9YBZ 功能、频谱和 FM，关闭短信/APRS。源码中的短信/APRS 保留，但本轮固件不启用。

英文完整配置：MIC_PF、自定义侧键、Talk Permit、MDC1200（含联系人/编辑/监听音）、VOX、FM、频谱；原装 EEPROM。GCC 15.2.0 原始镜像 61304 字节，剩余 136 字节。
中文最终配置（已获用户确认）：关闭 VOX 和 DTMF 呼叫，保留手咪 PF、Talk Permit、MDC1200（含联系人/编辑/监听音）、频谱及 FM，关闭短信/APRS，使用原装 EEPROM。原始镜像 59792 字节，剩余 1648 字节；正式输出到 artifacts/zh。
为支持关闭 DTMF 呼叫，修复 app/action.c 和 ui/main.c 中缺失的条件编译保护，不改变呼叫功能开启时的行为。英文版保留 VOX 和 DTMF 呼叫。

本轮不改变 Flash/bootloader 边界，不改变 EEPROM 要求。旧短信版已归档到仓库外 /home/yuhui/software_ws/uv-k5-build-history/merged-sms-23a1835。

复现（仓库根目录）：

```sh
docker build -t uvk5-toolchain:alpine3.23 -f scripts/Dockerfile.toolchain scripts
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/src" uvk5-toolchain:alpine3.23 sh scripts/build-merged.sh
```

中英文构建日志及正式产物分别位于 artifacts/zh、artifacts/en。firmware 为 ELF、firmware.bin 为原始镜像、W9YBZ*.bin 为打包刷机文件。
未进行真实设备的 PTT、手咪电阻梯、射频短信/APRS 及 EEPROM 兼容性测试；原 W9YBZ 文档中的手咪 PF/PTT 已知问题仍保留。

## 开机提示音

启动初始化和欢迎画面等待完成、可选开机密码流程结束、主界面及状态栏绘制完成后，播放一次 880Hz、约 200ms 的单声就绪提示音，独立于按键音开关，复用现有本地蜂鸣音流程。手咪调试与自定义引导分支在此之前处理。中英文均启用，不改变此前确认的功能配置。

## 外接手咪导致启动等待不结束

原逻辑在欢迎画面超时后仍等待 KEYBOARD_Poll() 返回 KEY_INVALID。手咪 ADC 若落入 PF1/PF2 范围会被锁存，直到连续两次达到松开阈值（3300）；不匹配手咪可能一直无法满足该条件。

修复：增加 KEYBOARD_PollPhysical()，启动期间的松键等待、EXIT 跳过及 F 调试入口只扫描机身按键。运行时 PF 首次按键前必须先检测到连续两次有效松开电压，避免把开机时的常低电平当作按键。正常 PF 的电压范围、按住/松开锁存及 UART 配置期间的旁路保持不变。

回归验证：`python3 tests/test_mic_pf_startup.py`。测试使用实际固件函数与模拟 ADC/GPIO，覆盖卡低启动、EXIT/F、PF 启用门槛、正常按住和松开、UART 旁路及 PA7 功能恢复。中英文构建及 CRC 校验通过；未用发生问题的实物手咪验证。

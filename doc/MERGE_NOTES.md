# W9YBZ + losehu 融合记录

本次为真实 Git 合并：W9YBZ `9c42b09`（18 个独有提交）与 losehu `49222a9`（7 个独有提交），共同祖先的两侧历史均保留。

保留 W9YBZ 的 Talk Permit TX 启动流程、KMC-25 ADC PF 按键及菜单、MDC1200 本地监听音量、切换提示音、全高信道名。
合入 losehu 的短信/APRS、消息历史与编辑交互、菜单边界、静噪溢出修复及寄存器批量写入优化。

冲突处理：中文 README 合并说明；菜单计数统一使用 UI_MENU_GetMenuCount，保留 TPTone、MDCMON、MPF 菜单项；去除重复的 MENU_GetListCount。
语义冲突处理：MIC_PF=1 时不再自动关闭自定义侧键，否则手咪 PF 菜单及 EEPROM 设置会被裁掉。
附带修复：发送模式枚举从 0 开始，避免原上游值超过 uint8_t 导致 APRS 分支及服务回执判断失效。
中英文输出分别命名 W9YBZ_KMC25-PF-ZH.bin 和 W9YBZ_KMC25-PF-EN.bin，避免互相覆盖。

## 当前可用固件配置

两版均为原装 EEPROM：保留 MIC_PF、自定义侧键、Talk Permit、MDC1200（含联系人/编辑/监听音）、VOX，开启 FM、短信/APRS/送达通知，关闭频谱。
源码仍包含频谱，通过 ENABLE_SPECTRUM 选择。全部功能同开超过 60KB Flash，不应使用扩大发送区或缩减 bootloader 的方式规避。
中文版以 -fipa-pta -finline-limit=5 -fmerge-all-constants 做体积优化；后一个选项允许常量存储合并。
GCC 15.2.0 下中文原始镜像 61436 字节（余 4 字节），英文 59220 字节（余 2220 字节）。
本次构建不沿用之前关闭 VOX 的 losehu-only 固件。

复现（仓库根目录）：

```sh
docker build -t uvk5-toolchain:alpine3.23 -f scripts/Dockerfile.toolchain scripts
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/src" uvk5-toolchain:alpine3.23 sh scripts/build-merged.sh
```

构建日志及产物位于 artifacts/en 和 artifacts/zh。firmware 为 ELF、firmware.bin 为原始镜像、W9YBZ*.bin 为打包刷机文件。
未进行真实设备的 PTT、手咪电阻梯、射频短信/APRS 及 EEPROM 兼容性测试；原 W9YBZ 文档中的手咪 PF/PTT 已知问题仍保留。

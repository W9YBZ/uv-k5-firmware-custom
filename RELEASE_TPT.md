# TPT Release (2026-02-01)

## Version
- Title: **TPT**
- Tag/Version: **TPT**

## Highlights
- Adds **Talk Permit Tone** menu (TPTone) and keeps it visible in the menu list.
- Fixes menu list truncation by deriving menu count from the actual `MenuList`.
- Enables **MDC1200** by default, including MDCID edit and contacts.

## Behavior Notes
- `MENU_ROGER` now appears between **MDCID** and **TPTone**.
- **MDCID** menu is accessible and editable with MDC1200 enabled.

## Build Artifacts
- `LOSEHU132_TPT.bin` (packed firmware for flashing)
- `firmware_TPT.bin` (raw binary)

## Source Changes
- `Makefile`: enable MDC1200 by default, add build tag/OUTPUT_TAG support.
- `main.c`, `ui/menu.c`, `ui/menu.h`: dynamic menu count (no truncation).

#!/usr/bin/env python3
"""Exercise resource merging without radio access, and the actual menu reader."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('assets', ROOT / 'scripts/eeprom-4m-assets.py')
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)
with tempfile.TemporaryDirectory() as temp:
    base = Path(temp)
    original = bytes(range(256)) * 2048
    backup = base / 'backup.bin'
    backup.write_bytes(original)
    directory = base / 'assets'
    directory.mkdir()
    spans = {0x2480: 1072, 0x2C00: 308, 0x2E00: 111590, 0x7F000: 42}
    records = []
    for address, length in spans.items():
        blob = bytes([address % 251]) * length
        name = f'{address:x}.bin'
        (directory / name).write_bytes(blob)
        records.append(dict(offset=address, length=length, file=name, sha256=hashlib.sha256(blob).hexdigest()))
    manifest = dict(eeprom_bytes=524288, menu_count=3, menu_bank=0x7F000, resources=records)
    (directory / 'resources.json').write_text(json.dumps(manifest))
    output = base / 'patched.bin'
    patched = assets.merge_backup(backup, directory, output)
    assert len(patched) == 524288 and backup.read_bytes() == original
    for i in range(524288):
        if not any(start <= i < start+length for start,length in spans.items()):
            assert patched[i] == original[i]
    assert patched[:0x2480] == original[:0x2480]  # calibration, settings, welcome/image
    def rejects(call):
        try:
            call()
        except (AssertionError, ValueError, FileExistsError):
            return
        raise AssertionError('Invalid operation accepted')
    rejects(lambda: assets.merge_backup(backup, directory, output))
    small = base / 'small.bin'
    small.write_bytes(original[:65536])
    rejects(lambda: assets.merge_backup(small, directory, base / 'bad.bin'))
    (directory / records[0]['file']).write_bytes(b'x' * records[0]['length'])
    rejects(lambda: assets.merge_backup(backup, directory, base / 'bad.bin'))
    assert not (base / 'bad.bin').exists()
    # Restore the blob before testing independent manifest errors.
    first = records[0]
    (directory / first['file']).write_bytes(bytes([first['offset'] % 251]) * first['length'])
    manifest['menu_count'] = 129
    (directory / 'resources.json').write_text(json.dumps(manifest))
    rejects(lambda: assets.merge_backup(backup, directory, base / 'bad.bin'))
    manifest['menu_count'] = 3
    manifest['resources'] = records[:-1]
    (directory / 'resources.json').write_text(json.dumps(manifest))
    rejects(lambda: assets.merge_backup(backup, directory, base / 'bad.bin'))
    manifest['resources'] = records
    (directory / first['file']).replace(base / first['file'])
    first['file'] = '../' + first['file']
    (directory / 'resources.json').write_text(json.dumps(manifest))
    rejects(lambda: assets.merge_backup(backup, directory, base / 'bad.bin'))
    assert not (base / 'bad.bin').exists()

    text = (ROOT / 'ui/menu.c').read_text()
    start = text.index('void UI_ShowChineseMenu()')
    end = text.index('\n}\n', start)+3
    function = text[start:end]
    harness = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
static unsigned gMenuCursor, show_move_flag;
static uint8_t is_chn(uint8_t c) { return 255; }
static void EEPROM_ReadBuffer(unsigned address, uint8_t *out, unsigned count) {
#ifdef ENABLE_EEPROM_4M
 assert(address == 0x7F000 + 14*gMenuCursor);
#else
 assert(address == 0x28B0 + 14*gMenuCursor);
#endif
 assert(count==14);
 memset(out, 'M', 14); /* Full-width resource must still be NUL terminated. */
}
static void UI_PrintStringSmall(const char *s, unsigned x, unsigned y, unsigned z) {
 assert(strlen(s)==14);
}
FUNCTION
int main(void) { gMenuCursor=90; UI_ShowChineseMenu(); assert(show_move_flag); }
'''.replace('FUNCTION', function)
    source = base / 'menu.c'
    source.write_text(harness)
    for expanded in (False, True):
        flags = ['-DENABLE_CHINESE_FULL=4'] + (['-DENABLE_EEPROM_4M'] if expanded else [])
        subprocess.run(['cc', '-std=c99', '-Werror', '-fsanitize=undefined,bounds', *flags, str(source), '-o', str(base / 'menu')], check=True)
        subprocess.run([str(base / 'menu')], check=True)
print('4M EEPROM preservation, rejection cases and actual menu reader passed')

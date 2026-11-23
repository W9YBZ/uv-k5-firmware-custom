#!/usr/bin/env python3
"""Generate expanded-Chinese resources or merge them into a real 512KiB backup.
This program only handles local files; it never accesses a radio or serial port.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SIZE = 524288
MENU_BASE = 0x7F000

def array_body(text, name, last=False):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    matches = list(re.finditer(r'\b' + re.escape(name) + r'\s*(?:\[[^\]]*\])*\s*=\s*\{', text))
    match = matches[-1 if last else 0]
    start, end, depth = match.end(), match.end(), 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end-1]

def values(body):
    return [int(v, 0) for v in re.findall(r'0[xX][0-9A-Fa-f]+|\b[0-9]+\b', body)]

def gb_font():
    source = (ROOT / 'uv-k5font/uv-k5font_full/font.cpp').read_text().split('#else', 1)[0]
    names = re.findall(r'/\*([^*]*)\*/', source)
    codes = []
    for hi in range(0xB0, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                codes.append(bytes([hi, lo]).decode('gb2312'))
            except UnicodeDecodeError:
                pass
    assert [re.sub(r'\d+$', '', n) for n in names] == codes
    glyphs = bytes(values(array_body(source, 'new_font')))
    assert len(glyphs) == 6763 * 22
    packed = bytearray((6763 * 132 + 7) // 8)
    bit = 0
    for i, column in enumerate(glyphs):
        for j in range(8 if i % 22 < 11 else 4):
            if column & (1 << j):
                packed[bit // 8] |= 1 << (bit % 8)
            bit += 1
    # Decode in the same column/page order as ui/helper.c, checking every glyph.
    bit = 0
    for i, column in enumerate(glyphs):
        width = 8 if i % 22 < 11 else 4
        decoded = 0
        for j in range(width):
            decoded |= ((packed[bit // 8] >> (bit % 8)) & 1) << j
            bit += 1
        assert decoded == column & ((1 << width) - 1)
    return bytes(packed)

def menu_names(flags_path):
    flags = []
    for line in flags_path.read_text().splitlines():
        flags.extend(t for t in shlex.split(line) if t.startswith('-DENABLE_'))
    source = (ROOT / 'ui/menu.c').read_text()
    start = source.index('const t_menu_item MenuList[]')
    table = source[start:source.index('};', start) + 2]
    expanded = subprocess.check_output(['arm-none-eabi-gcc', '-E', '-P', '-x', 'c', '-I', str(ROOT),
                                        *flags, '-'], input='#include "chinese.h"\n' + table, text=True)
    body = array_body(expanded, 'MenuList')
    labels = []
    for entry in re.findall(r'\{([^{}]*)\}', body):
        strings = re.findall(r'"(?:\\.|[^"\\])*"', entry)
        labels.append(b''.join(ast.literal_eval('b' + s) for s in strings))
    assert labels[-1] == b'\0'
    labels.pop()
    output = bytearray()
    for label in labels:
        assert label and b'\0' not in label
        encoded = bytearray()
        for character in label.decode('gb2312'):
            piece = character.encode('gb2312')
            if len(encoded) + len(piece) > 14:
                break
            encoded.extend(piece)
        output.extend(bytes(encoded).ljust(14, b'\0'))
    assert len(labels) <= 128
    return bytes(output), len(labels)

def generate(flags_path, output):
    output.mkdir(parents=True, exist_ok=True)
    fonts = (ROOT / 'font.c').read_text()
    ascii_fonts = b''.join(bytes(values(array_body(fonts, name))) for name in
                           ('gFontBigDigits', 'gFont3x5', 'gFontSmall'))
    assert len(ascii_fonts) == 220 + 288 + 564
    tones = (ROOT / 'dcs.c').read_text()
    ctcss = values(array_body(tones, 'CTCSS_Options', last=True))
    dcs = values(array_body(tones, 'DCS_Options'))
    assert len(ctcss) == 50 and ctcss[0] == 670 and len(dcs) == 104
    tone_data = struct.pack('<154H', *(ctcss + dcs))
    names, count = menu_names(flags_path)
    resources = [(0x2480, 'ascii-fonts.bin', ascii_fonts), (0x2C00, 'tone-tables.bin', tone_data),
                 (0x2E00, 'gb2312-font.bin', gb_font()), (MENU_BASE, 'menu-names.bin', names)]
    records = []
    for address, name, data in resources:
        (output / name).write_bytes(data)
        records.append({'offset': address, 'length': len(data), 'file': name,
                        'sha256': hashlib.sha256(data).hexdigest()})
    manifest = {'eeprom_bytes': SIZE, 'menu_count': count, 'menu_bank': MENU_BASE,
                'font_format': '11x12, 6763 GB2312 simplified glyphs, column/page LSB-first',
                'resources': records}
    (output / 'resources.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'4M resources: {count} menus, complete GB2312 and ASCII fonts, CTCSS/DCS tables')
    return manifest

def merge_backup(backup, assets, destination):
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    original = Path(backup).read_bytes()
    if len(original) != SIZE:
        raise ValueError('A complete 524288-byte 4Mbit EEPROM backup is required; 64KiB dumps are not accepted')
    manifest = json.loads((Path(assets) / 'resources.json').read_text())
    require(manifest['eeprom_bytes'] == SIZE, 'Wrong EEPROM size in manifest')
    require(0 < manifest['menu_count'] <= 128 and manifest['menu_bank'] == MENU_BASE, 'Invalid menu bank/count')
    allowed = {0x2480: 1072, 0x2C00: 308, 0x2E00: 111590, MENU_BASE: manifest['menu_count'] * 14}
    patched = bytearray(original)
    seen = set()
    for record in manifest['resources']:
        address, length = record['offset'], record['length']
        require(address not in seen and allowed.get(address) == length and address + length <= SIZE, 'Invalid or duplicate resource range')
        seen.add(address)
        path = Path(assets) / record['file']
        require(path.resolve().parent == Path(assets).resolve(), 'Resource must be inside the asset directory')
        data = path.read_bytes()
        require(len(data) == length and hashlib.sha256(data).hexdigest() == record['sha256'], 'Resource length/hash mismatch')
        patched[address:address+length] = data
    require(seen == set(allowed) and patched[:0x2000] == original[:0x2000], 'Missing resources or changed settings')
    # Verify every gap, not just the channel/calibration area.
    previous = 0
    for address, length in sorted(allowed.items()):
        require(patched[previous:address] == original[previous:address], 'Changed bytes outside resource ranges')
        previous = address + length
    require(patched[previous:] == original[previous:], 'Changed bytes outside resource ranges')
    with Path(destination).open('xb') as stream:
        stream.write(patched)
    return bytes(patched)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    gen = sub.add_parser('generate')
    gen.add_argument('--flags', type=Path, required=True)
    gen.add_argument('--output', type=Path, required=True)
    apply = sub.add_parser('apply')
    apply.add_argument('--backup', type=Path, required=True)
    apply.add_argument('--assets', type=Path, required=True)
    apply.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'generate':
        generate(args.flags, args.output)
    else:
        merge_backup(args.backup, args.assets, args.output)
        print('Created a separate patched backup; all bytes outside resource ranges are unchanged. No device was accessed.')

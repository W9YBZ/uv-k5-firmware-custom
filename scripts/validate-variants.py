#!/usr/bin/env python3
"""Validate packed firmware and actual compiler flags for one or all profiles."""
import ast
import binascii
import hashlib
import json
from pathlib import Path
import shlex
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/variants'
PROFILES = {
    'standard': {'zh': (0, 0, 0, 1), 'en': (1, 1, 0, 1)},
    'call': {'zh': (1, 1, 0, 0), 'en': (1, 1, 0, 0)},
    'messaging': {'zh': (0, 1, 1, 0), 'en': (1, 1, 1, 0)},
}

def validate(profile, language):
    vox, dtmf, message, spectrum = PROFILES[profile][language]
    suffix = {'standard': 'W9YBZ_KMC25-PF', 'call': 'W9YBZ-CALL', 'messaging': 'W9YBZ-MSG'}[profile]
    suffix += '-' + language.upper()
    directory = BASE / profile / language
    path = directory / (suffix + '.bin')
    packed = path.read_bytes()
    raw = (directory / 'firmware.raw.bin').read_bytes()
    flags = {}
    for line in (directory / 'compiler-flags.txt').read_text().splitlines():
        for token in shlex.split(line):
            if token.startswith('-D'):
                name, _, value = token[2:].partition('=')
                flags[name] = value or '1'
    expected = {
        'ENABLE_CHINESE_FULL': '0', 'ENABLE_EEPROM_TYPE': '0',
        'ENABLE_MIC_PF': '1', 'ENABLE_CUSTOM_SIDEFUNCTIONS': '1',
        'ENABLE_SIDEFUNCTIONS_SEND': '1', 'ENABLE_MDC1200': '1',
        'ENABLE_MDC1200_EDIT': '1', 'ENABLE_MDC1200_CONTACT': '1',
        'ENABLE_MDC1200_SIDE_BEEP': '1', 'ENABLE_FMRADIO': '1',
        'ENABLE_ENGLISH': str(int(language == 'en')),
        'ENABLE_VOX': str(vox), 'ENABLE_DTMF_CALLING': str(dtmf),
        'ENABLE_MESSENGER': str(message), 'ENABLE_SPECTRUM': str(spectrum),
        'ENABLE_MESSENGER_DELIVERY_NOTIFICATION': str(message),
        'ENABLE_MESSENGER_NOTIFICATION': str(message),
    }
    for name, value in expected.items():
        # Disabled feature flags are omitted; numeric EEPROM/font selectors remain defined.
        assert flags.get(name, '0') == value, (name, flags.get(name), value)
    assert flags['PACKED_FILE_SUFFIX'] == suffix
    assert not any(flags.get(k, '0') != '0' for k in ('ENABLE_PINYIN', 'ENABLE_DOPPLER', 'ENABLE_4732', 'ENABLE_BOOTLOADER'))
    tree = ast.parse((ROOT / 'fw-pack.py').read_text())
    key = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == 'OBFUSCATION' for t in n.targets))
    assert 8192 < len(raw) <= 61440
    assert len(packed) == len(raw) + 18
    assert binascii.crc_hqx(packed[:-2], 0) == int.from_bytes(packed[-2:], 'little')
    decoded = bytes(value ^ key[i % len(key)] for i, value in enumerate(packed[:-2]))
    assert decoded[8192:8208] == b'*OEFW-LOSEHU'.ljust(16, b'\0')
    assert decoded[:8192] + decoded[8208:] == raw
    for marker in (b'TPTone', b'MDCMON', b'MPF1S', b'MPF1L', b'MPF2S', b'MPF2L', b'VOL', suffix.encode()):
        assert marker in raw, (profile, language, marker)
    assert (b'DOWN:APRS' in raw) == bool(message)
    # Cross-check that the raw image is the load image of the accompanying ELF.
    subprocess.run(['arm-none-eabi-objcopy', '-O', 'binary', str(directory / 'firmware.elf'),
                    str(directory / '.elf-check.bin')], check=True)
    try:
        assert (directory / '.elf-check.bin').read_bytes() == raw
    finally:
        (directory / '.elf-check.bin').unlink(missing_ok=True)
    symbols = subprocess.check_output(['arm-none-eabi-nm', str(directory / 'firmware.elf')], text=True)
    assert (' rssiHistory' in symbols) == bool(spectrum)
    initial_sp, reset_vector = struct.unpack_from('<II', raw)
    assert 0x20000000 < initial_sp <= 0x20004000 and reset_vector & 1
    assert (reset_vector & ~1) < len(raw)
    commit = (directory / 'source-commit.txt').read_text().strip()
    dirty = (directory / 'source-dirty.txt').read_text().strip() == 'true'
    manifest = {
        'profile': profile, 'language': language, 'source_commit': commit,
        'tracked_source_dirty': dirty, 'firmware': path.name,
        'raw_bytes': len(raw), 'packed_bytes': len(packed), 'flash_free_bytes': 61440 - len(raw),
        'sha256': hashlib.sha256(packed).hexdigest(), 'features': expected,
        'eeprom_layout': 'unchanged; existing low-address settings and calibration',
        'checks': ['compiler flags', '60KiB flash limit', 'CRC-XMODEM', 'pack/decode round trip',
                   'ELF/raw equality', 'boot vector', 'W9YBZ menus', 'messenger/spectrum selection'],
    }
    (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'{profile}/{language}: raw {len(raw)}, free {61440-len(raw)} bytes; all checks passed')
    return manifest

if __name__ == '__main__':
    if len(sys.argv) == 3:
        validate(*sys.argv[1:])
    elif len(sys.argv) == 1:
        results = [validate(profile, language) for profile in PROFILES for language in ('zh', 'en')]
        (BASE / 'manifest.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
        (BASE / 'SHA256SUMS.txt').write_text(''.join(
            f"{m['sha256']}  {m['profile']}/{m['language']}/{m['firmware']}\n" for m in results))
        with zipfile.ZipFile(BASE / 'W9YBZ-firmware-variants.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
            for m in results:
                directory = BASE / m['profile'] / m['language']
                relative = Path(m['profile']) / m['language']
                for filename in (m['firmware'], 'manifest.json'):
                    bundle.write(directory / filename, relative / filename)
            for filename in ('manifest.json', 'SHA256SUMS.txt'):
                bundle.write(BASE / filename, filename)
            bundle.write(ROOT / 'doc/FIRMWARE_VARIANTS.md', 'README.md')
        print('Bundle: artifacts/variants/W9YBZ-firmware-variants.zip')
    else:
        raise SystemExit('Usage: validate-variants.py [profile language]')

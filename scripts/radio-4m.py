#!/usr/bin/env python3
"""W9YBZ 4M EEPROM backup/resource installer. Normal powered-on radio, 38400 baud.
No port is opened without an explicit command. Install backs up before writing,
limits writes to four resource ranges and verifies the entire EEPROM afterward.
"""
import argparse
import binascii
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import time

spec = importlib.util.spec_from_file_location('eeprom_assets', Path(__file__).with_name('eeprom-4m-assets.py'))
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)
KEY = bytes.fromhex('166c14e62e910d402135d5401303e980')
VERSIONS = {'W9-4M-SPEC-ZH', 'W9-4M-CALL-ZH', 'W9-4M-MSG-ZH'}
STAMP = 0xFFFFFFFF
SIZE = 524288
CHUNK = 64

def xor(data):
    return bytes(value ^ KEY[i % 16] for i, value in enumerate(data))

def frame(payload):
    crc = struct.pack('<H', binascii.crc_hqx(payload, 0))
    return b'\xab\xcd' + struct.pack('<H', len(payload)) + xor(payload + crc) + b'\xdc\xba'

class Radio:
    def __init__(self, port):
        self.port = port
        self.buffer = bytearray()
        self.version = ''

    def exchange(self, payload, expected):
        packet = frame(payload)
        for start in range(0, len(packet), 64):
            chunk = packet[start:start+64]
            if self.port.write(chunk) != len(chunk):
                raise OSError('Short serial write; stopped')
            self.port.flush()
            time.sleep(.002)
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            while len(self.buffer) >= 4:
                if self.buffer[:2] != b'\xab\xcd':
                    del self.buffer[0]
                    continue
                length = struct.unpack_from('<H', self.buffer, 2)[0]
                if not 4 <= length <= 256:
                    del self.buffer[0]
                    continue
                if len(self.buffer) < length + 8:
                    break
                packet = bytes(self.buffer[:length+8])
                del self.buffer[:length+8]
                if packet[-2:] != b'\xdc\xba':
                    raise ValueError('Bad serial response footer; stopped')
                reply = xor(packet[4:-2])
                # Firmware replies use FF FF padding, NOT a reply CRC (SendReply).
                if reply[-2:] != b'\xff\xff':
                    raise ValueError('Bad serial response padding; stopped')
                reply = reply[:-2]
                command, declared = struct.unpack_from('<HH', reply)
                if command != expected:
                    continue
                if declared != len(reply)-4:
                    raise ValueError('Wrong response length; stopped')
                return reply
            self.buffer.extend(self.port.read(max(1, min(self.port.in_waiting, 512))))
        raise TimeoutError('No valid reply in 4s. Close K5Web/CHIRP, check cable and firmware; no automatic retries.')

    def hello(self):
        reply = self.exchange(struct.pack('<HHI', 0x0514, 4, STAMP), 0x0515)
        if len(reply) < 20:
            raise ValueError('Version response too short')
        self.version = reply[4:20].split(b'\0', 1)[0].decode('ascii')
        return self.version

    def read(self, address, size, expanded=True):
        if not (0 < size <= CHUNK and 0 <= address < SIZE and address+size <= SIZE):
            raise ValueError('Invalid read range')
        if not expanded and address+size > 8192:
            raise ValueError('Basic backup only reads the original 8KiB')
        offset = address >> 16 if expanded else address
        command = 0x052B if expanded else 0x051B
        request = struct.pack('<HHHBBI', command, 8, offset, size, 0, STAMP)
        if expanded:
            request += struct.pack('<H', address & 0xFFFF)
        reply = self.exchange(request, 0x051C)
        if len(reply) != 8+size or struct.unpack_from('<H', reply, 4)[0] != offset or reply[6] != size:
            raise ValueError('EEPROM read response does not match request')
        return reply[8:]

    def write(self, address, data):
        # These upper bounds also reject writes to settings/calibration/welcome data.
        ranges = ((0x2480, 0x28B0), (0x2C00, 0x2D34), (0x2E00, 0x1E1E6), (0x7F000, 0x7F700))
        if self.version not in VERSIONS or not 0 < len(data) <= CHUNK:
            raise ValueError('Unsupported firmware or write size')
        if not any(start <= address and address+len(data) <= end for start,end in ranges):
            raise ValueError('Write is outside the allowed resource ranges')
        # Header.Size is fixed at 28 by the inherited losehu extended protocol.
        payload = struct.pack('<HHHBBIH', 0x0538, 28, address >> 16, len(data)+2, 0, STAMP, address & 0xFFFF) + data
        reply = self.exchange(payload, 0x051E)
        if len(reply) != 6 or struct.unpack_from('<H', reply, 4)[0] != address >> 16:
            raise ValueError('EEPROM write acknowledgement does not match request')
        if self.read(address, len(data)) != data:
            raise ValueError(f'EEPROM write/readback mismatch at 0x{address:X}; stopped. Keep the backup.')

def progress(label, done, total):
    if done == total or done % 8192 == 0:
        print(f'{label}: {done}/{total} ({done*100/total:.1f}%)', flush=True)

def backup_radio(radio, destination, size=SIZE):
    destination = Path(destination)
    partial = destination.with_name(destination.name + '.partial')
    if destination.exists() or partial.exists():
        raise FileExistsError('Choose a NEW backup filename; existing backups and partial files are never overwritten')
    if size == SIZE and radio.version not in VERSIONS:
        raise ValueError('Full backup requires W9-4M-SPEC-ZH/CALL-ZH/MSG-ZH; use --size 8192 before flashing a 4M build')
    content = bytearray()
    with partial.open('xb') as stream:
        for address in range(0, size, CHUNK):
            data = radio.read(address, min(CHUNK, size-address), expanded=(size == SIZE))
            stream.write(data)
            content.extend(data)
            progress('Backup', len(content), size)
        stream.flush()
        os.fsync(stream.fileno())
    # Replies have no CRC. Require two matching reads before accepting the backup.
    for address in range(0, size, CHUNK):
        count = min(CHUNK, size-address)
        if radio.read(address, count, expanded=(size == SIZE)) != content[address:address+count]:
            raise ValueError(f'Backup repeated-read mismatch at 0x{address:X}; no installation started. Partial backup kept.')
        progress('Verify backup', address+count, size)
    # Exclusive creation also protects against another process creating the target.
    with destination.open('xb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    partial.unlink()
    checksum = hashlib.sha256(content).hexdigest()
    destination.with_name(destination.name + '.sha256').write_text(f'{checksum}  {destination.name}\n')
    print(f'Backup saved: {destination} ({size} bytes), SHA256 {checksum}', flush=True)
    return bytes(content)

def install(radio, directory, backup):
    manifest, resources = assets.load_resources(directory)
    if radio.version not in VERSIONS or manifest.get('firmware_version') != radio.version:
        raise ValueError('Resource/firmware version mismatch. Use the resources matching the installed W9-4M firmware.')
    original = backup_radio(radio, backup)
    expected = bytearray(original)
    total = sum(len(data) for data in resources.values())
    done = 0
    for address, data in sorted(resources.items()):
        expected[address:address+len(data)] = data
        for offset in range(0, len(data), CHUNK):
            piece = data[offset:offset+CHUNK]
            # Skip already correct bytes to reduce unnecessary EEPROM writes.
            if original[address+offset:address+offset+len(piece)] != piece:
                radio.write(address+offset, piece)
            done += len(piece)
            progress('Resources', done, total)
    for address in range(0, SIZE, CHUNK):
        actual = radio.read(address, min(CHUNK, SIZE-address))
        if actual != expected[address:address+len(actual)]:
            raise ValueError(f'Full EEPROM verification failed at 0x{address:X}. Keep the backup; stopped.')
        progress('Verify all EEPROM', address+len(actual), SIZE)
    print('PASS: all resource bytes match; every byte outside resource ranges matches the saved backup. Power-cycle the radio.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True, help='COM3 on Windows, /dev/ttyUSB0 on Linux, etc.')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('info')
    backup = sub.add_parser('backup')
    backup.add_argument('--output', type=Path, required=True)
    backup.add_argument('--size', type=int, choices=(8192, SIZE), default=SIZE)
    write = sub.add_parser('install')
    write.add_argument('--assets', type=Path, required=True)
    write.add_argument('--backup', type=Path, required=True, help='NEW path for automatic full backup before any EEPROM write')
    args = parser.parse_args()
    try:
        import serial
    except ImportError:
        parser.error('Install pyserial first: python -m pip install pyserial')
    # Validate local assets before even opening the serial port.
    if args.command == 'install':
        assets.load_resources(args.assets)
    port = serial.Serial(port=None, baudrate=38400, timeout=.2, write_timeout=4)
    port.dtr = False
    port.rts = False
    port.port = args.port
    with port:
        port.reset_input_buffer()
        radio = Radio(port)
        print('Firmware:', radio.hello(), flush=True)
        if args.command == 'backup':
            backup_radio(radio, args.output, args.size)
        elif args.command == 'install':
            install(radio, args.assets, args.backup)

if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(f'STOPPED: {error}. Any saved backup/partial file was kept. No automatic retry or reset.', file=sys.stderr)
        sys.exit(1)

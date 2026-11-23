#!/usr/bin/env python3
"""Protocol and interrupted-install tests; no physical serial port is opened."""
import importlib.util
from pathlib import Path
import struct
import tempfile
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('radio4m', ROOT / 'scripts/radio-4m.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.progress = lambda *args: None
m.time.sleep = lambda seconds: None
# Golden request layout matches app/uart.c and K5Web serial.c484fd9f.js.
assert m.binascii.crc_hqx(b'123456789', 0) == 0x31C3
class FakePort:
    def __init__(self):
        self.requests = bytearray()
        self.pending = bytearray()
        self.memory = bytearray(bytes(range(256))*2048)
        self.writes = []
        self.bad_readback = False
        self.version = b'W9-4M-SPEC-ZH'
        self.truncate = False
    @property
    def in_waiting(self): return len(self.pending)
    def flush(self): pass
    def write(self, data):
        self.requests.extend(data)
        if len(self.requests)<4: return len(data)
        length = struct.unpack_from('<H', self.requests, 2)[0]
        if len(self.requests) < length+8: return len(data)
        packet = bytes(self.requests)
        self.requests.clear()
        assert packet[:2]==b'\xab\xcd' and packet[-2:]==b'\xdc\xba'
        payload = m.xor(packet[4:-2])
        assert m.binascii.crc_hqx(payload[:-2],0)==int.from_bytes(payload[-2:],'little')
        payload=payload[:-2]
        command,declared = struct.unpack_from('<HH', payload)
        if command==0x0514:
            assert payload==bytes.fromhex('14050400ffffffff')
            body = self.version.ljust(16,b'\0') + bytes(20)
            reply = struct.pack('<HH',0x0515,len(body)) + body
        elif command in (0x052B,0x051B):
            bank,count=struct.unpack_from('<HB',payload,4)
            assert declared==8 and payload[8:12]==bytes.fromhex('ffffffff')
            address = (bank<<16)+int.from_bytes(payload[12:14],'little') if command==0x052B else bank
            result = bytes(self.memory[address:address+count])
            if self.bad_readback and self.writes:
                result = bytes([result[0]^1])+result[1:]
            reply = struct.pack('<HHHBB',0x051C,4+count,bank,count,0)+result
        elif command==0x0538:
            bank,count=struct.unpack_from('<HB',payload,4)
            assert declared==28 and payload[8:12]==bytes.fromhex('ffffffff')
            address = (bank<<16)+int.from_bytes(payload[12:14],'little')
            result = payload[14:]
            assert len(result)==count-2
            self.memory[address:address+len(result)]=result
            self.writes.append((address,result))
            # sizeof(REPLY_051D_t) is SIX bytes, not eight.
            reply = struct.pack('<HHH',0x051E,2,bank)
        else: raise AssertionError(command)
        if self.truncate: reply=reply[:-1]
        self.pending.extend(b'\xab\xcd'+struct.pack('<H',len(reply))+m.xor(reply+b'\xff\xff')+b'\xdc\xba')
        return len(data)
    def read(self,size):
        # Fragment every response, including headers and footer.
        result=bytes(self.pending[:min(size,7)])
        del self.pending[:len(result)]
        return result

def reject(call, kind=ValueError):
    try: call()
    except kind: return
    raise AssertionError('Invalid operation accepted')

# Port framing and full high-address roundtrip, including a partial final block.
p=FakePort(); r=m.Radio(p); assert r.hello()=='W9-4M-SPEC-ZH'
r.read(0x7F000,64)
r.write(0x7F000,b'Example menu'.ljust(14,b'\0'))
r.write(0x1E1E0,b'123456')
assert len(p.writes)==2
reject(lambda:r.write(0x1FFF,b'bad'))
reject(lambda:r.write(0x7F6FF,b'xx'))
assert len(p.writes)==2
p.bad_readback=True
reject(lambda:r.write(0x2480,b'xx'))
# A malformed reply cannot be accepted even when the command ID is right.
p=FakePort(); p.truncate=True
reject(lambda:m.Radio(p).hello())
with tempfile.TemporaryDirectory() as tmp:
    base=Path(tmp)
    resource_dir=ROOT/'artifacts/4m/spectrum/zh/eeprom-assets'
    p=FakePort(); r=m.Radio(p); r.hello()
    old=bytes(p.memory)
    m.install(r,resource_dir,base/'backup.bin')
    assert (base/'backup.bin').read_bytes()==old
    assert len(p.memory)==524288 and p.writes
    _,resources=m.assets.load_resources(resource_dir)
    expected=bytearray(old)
    for address,data in resources.items(): expected[address:address+len(data)]=data
    assert p.memory==expected
    assert p.memory[:0x2480]==old[:0x2480]
    writes=len(p.writes)
    reject(lambda:m.install(r,resource_dir,base/'backup.bin'),FileExistsError)
    assert len(p.writes)==writes
    # Matching resource set already installed: take a new backup, no EEPROM writes.
    m.install(r,resource_dir,base/'second.bin')
    assert len(p.writes)==writes
    p.version=b'W9-4M-CALL-ZH'; r.hello()
    reject(lambda:m.install(r,resource_dir,base/'wrong-profile.bin'))
    assert not (base/'wrong-profile.bin').exists() and len(p.writes)==writes
    p=FakePort(); p.bad_readback=True; r=m.Radio(p);r.hello()
    reject(lambda:m.install(r,resource_dir,base/'before-failure.bin'))
    assert len(p.writes)==1 and (base/'before-failure.bin').read_bytes()==old
    # A mismatch between the two pre-write backup reads prevents ALL writes.
    p=FakePort();r=m.Radio(p);r.hello()
    real_read=r.read
    count=[0]
    def unstable(address,size,expanded=True):
        result=real_read(address,size,expanded)
        count[0]+=1
        if count[0]==8193:
            return bytes([result[0]^1])+result[1:]
        return result
    r.read=unstable
    reject(lambda:m.install(r,resource_dir,base/'unstable.bin'))
    assert not p.writes and not (base/'unstable.bin').exists()
    assert (base/'unstable.bin.partial').stat().st_size==524288
    # Basic backup can be read on a standard build, using only the 16-bit command.
    p=FakePort();p.version=b'W9YBZ-CALL-ZH';r=m.Radio(p);r.hello()
    assert m.backup_radio(r,base/'basic.bin',8192)==bytes(p.memory[:8192])
    reject(lambda:m.backup_radio(r,base/'full.bin'))
    assert not p.writes
print('Protocol framing, high banks, six-byte ACK, full backup/install, preservation and failure-stop tests passed')

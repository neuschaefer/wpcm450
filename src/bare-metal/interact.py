#!/usr/share/python3
# SPDX-License-Identifier: MIT
# Usage: python3 -i ./interact.py

import serial, time, re, struct, sys

class Lolmon:
    def __init__(self, device):
        self.device = device
        self.s = serial.Serial(device, baudrate=115200)
        self.prompt = b'> '
        self.debug = False

    def connection_test(self):
        self.s.write(b'\n')
        time.sleep(0.2)
        answer = self.s.read_all()
        if (b'\r\n' + self.prompt) in answer:
            print("lolmon detected!")

    def read_until_prompt(self):
        answer = bytearray()
        timeout = 1
        while True:
            if self.s.readable():
                answer += self.s.read_all()
                if self.prompt in answer:
                    return bytes(answer)[:-len(self.prompt)], True
            else:
                time.sleep(0.05)
                timeout -= 0.05

            if timeout < 0:
                return bytes(answer), False

    def flush(self):
        self.s.read_all()

    def enter_with_echo(self, cmd):
        if isinstance(cmd, str):
            cmd = cmd.encode('UTF-8')
        assert not b'\n' in cmd

        pos = 0
        while pos < len(cmd):
            chunk = cmd[pos:pos+8]
            assert len(chunk) >= 1
            self.s.write(chunk)
            echo = self.s.read(len(chunk))
            if echo != chunk:
                print('Echo error! %s != %s' % (echo, chunk))
            pos += len(chunk)

    def run_command(self, cmd):
        if self.debug:
            print(':> %s' % cmd)
        self.enter_with_echo(cmd)

        self.s.write(b'\n')
        assert self.s.read(2) == b'\r\n'

        answer, good = self.read_until_prompt()
        if not good:
            print('Command \'%s\' timed out:\n%s' % (cmd, answer.decode('UTF-8')))
            return b''
        return answer

    def writeX(self, cmd, size, addr, value):
        #print('poke %s %08x %s' % (cmd, addr, value))
        if isinstance(value, bytes):
            value = [x for x in value]
        if isinstance(value, list):
            for v in value:
                self.writeX(cmd, size, addr, v)
                addr += size
        else:
            self.run_command("%s %08x %#x" % (cmd, addr, value))

    def write8(self, addr, value):  return self.writeX('wb', 1, addr, value)
    def write16(self, addr, value): return self.writeX('wh', 2, addr, value)
    def write32(self, addr, value): return self.writeX('ww', 4, addr, value)

    def memset(self, addr, value, size):
        value16 = value << 8 | value
        value32 = value16 << 16 | value16
        while size > 0:
            if addr & 3 != 0 or size < 4:
                n = size & 3 or 1
                self.write8(addr, [value] * n)
                addr += n
                size -= n
            else:
                n = size // 4
                self.write32(addr, [value32] * n)
                addr += n * 4
                size -= n * 4

    def parse_r_output(self, s):
        array = []
        s = s.decode('UTF-8')
        for line in s.splitlines():
            if re.match('[0-9a-f]{8}: [0-9a-f]+', line):
                for n in line[10:].split(' '):
                    array.append(int(n, base=16))
        return array


    def readX(self, cmd, size, addr, num):
        output = self.run_command("%s %08x %d" % (cmd, addr, num))
        a = self.parse_r_output(output)
        if num == 1: return a[0]
        else:        return a

    def read8(self, addr, num=1):  return self.readX('rb', 1, addr, num)
    def read16(self, addr, num=1): return self.readX('rh', 2, addr, num)
    def read32(self, addr, num=1): return self.readX('rw', 4, addr, num)

    def make_setclr(rd, wr):
        def fn(self, addr, bit, value):
            x = rd(self, addr)
            if value: wr(self, addr, x |  (1 << bit))
            else:     wr(self, addr, x & ~(1 << bit))
        return fn

    setclr8 = make_setclr(read8, write8)
    setclr16 = make_setclr(read16, write16)
    setclr32 = make_setclr(read32, write32)

    def make_dump(cmd):
        def fn(self, addr, length):
            res = self.run_command('%s %08x %d' % (cmd, addr, length))
            print(res.decode('ascii').strip())
        return fn

    dump8 = make_dump('rb')
    dump16 = make_dump('rh')
    dump32 = make_dump('rw')


class Block:
    def __init__(self, lolmon, base=None):
        self.l = lolmon
        if base:
            self.base = base

    def read8(self, offset): return self.l.read8(self.base + offset)
    def read16(self, offset): return self.l.read16(self.base + offset)
    def read32(self, offset): return self.l.read32(self.base + offset)

    def write8(self, offset, value): return self.l.write8(self.base + offset, value)
    def write16(self, offset, value): return self.l.write16(self.base + offset, value)
    def write32(self, offset, value): return self.l.write32(self.base + offset, value)

    def setclr8(self, offset, bit, value): return self.l.setclr8(self.base + offset, bit, value)
    def setclr16(self, offset, bit, value): return self.l.setclr16(self.base + offset, bit, value)
    def setclr32(self, offset, bit, value): return self.l.setclr32(self.base + offset, bit, value)

    def dump(self):
        self.l.dump32(self.base, 0x20)


class Clocks(Block):
    CLKEN     = 0x00
    CLKSEL    = 0x04
    IPSRST    = 0x20

    def reset(self, line, value):
        self.setclr32(self.IPSRST, line, value)

    def clken(self, line, value):
        self.setclr32(self.CLKEN, line, value)

class SHM(Block):
    def dump(self):
        self.l.dump8(self.base, 0x20)

class RNG(Block):
    CMD = 0
    DATA = 4
    MODE = 8

GCR = MC = EMC = USB = KCS = FIU = KCS = GDMA = AES = UART = SMB = PWM = MFT = Block
PECI = GFXI = SSPI = Timers = AIC = GPIO = ADC = SDHC = ROM = Block


l = Lolmon('/dev/ttyUSB0')
l.connection_test()
gcr  = GCR(l, 0xb0000000)
clk  = Clocks(l, 0xb0000200)
mc   = MC(l, 0xb0001000)
emc0 = EMC(l, 0xb0002000)
emc1 = EMC(l, 0xb0003000)
gdma = GDMA(l, 0xb0004000)
usb0 = USB(l, 0xb0005000)
usb1 = USB(l, 0xb0006000)
sdhc = SDHC(l, 0xb0007000)
uart0= UART(l, 0xb8000000)
uart1= UART(l, 0xb8000100)
peci = PECI(l, 0xb8000200)
gfxi = GFXI(l, 0xb8000300)
sspi = SSPI(l, 0xb8000400)
tmr  = Timers(l, 0xb8001000)
aic  = AIC(l, 0xb8002000)
gpio = GPIO(l, 0xb8003000)
mft0 = MFT(l, 0xb8004000)
mft1 = MFT(l, 0xb8005000)
smb0 = SMB(l, 0xb8006000)
smb1 = SMB(l, 0xb8006100)
smb2 = SMB(l, 0xb8006200)
smb3 = SMB(l, 0xb8006300)
smb4 = SMB(l, 0xb8006400)
smb5 = SMB(l, 0xb8006500)
pwm  = PWM(l, 0xb8007000)
kcs  = KCS(l, 0xb8008000)
adc  = ADC(l, 0xb8009000)
rng  = RNG(l, 0xb800a000)
aes  = AES(l, 0xb800b000)
fiu  = FIU(l, 0xc8000000)
shm  = SHM(l, 0xc8001000)
rom  = ROM(l, 0xffff0000)

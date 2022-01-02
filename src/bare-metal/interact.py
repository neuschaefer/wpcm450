#!/usr/share/python3
# SPDX-License-Identifier: MIT
# Usage: python3 -i ./interact.py

import serial, time, re, struct, sys, random, socket, os

def BIT(x):
    return 1 << x

def MASK(x):
    return BIT(x) - 1

def bswap16(x):
    x = (x & 0xff00ff00) >>  8 | (x & 0x00ff00ff) <<  8
    return x

def bswap32(x):
    x = (x & 0xffff0000) >> 16 | (x & 0x0000ffff) << 16
    x = (x & 0xff00ff00) >>  8 | (x & 0x00ff00ff) <<  8
    return x

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
        while self.s.read_all() != b'':
            time.sleep(0.05)
        self.run_command('')

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
        try:
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
        except KeyboardInterrupt as e:
            time.sleep(0.10)
            self.flush()
            raise e

    def run_command_noreturn(self, cmd):
        if self.debug:
            print(':> %s' % cmd)
        self.enter_with_echo(cmd)
        self.s.write(b'\n')
        assert self.s.read(2) == b'\r\n'

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
        else:        return bytes(a)

    def read8(self, addr, num=1):  return self.readX('rb', 1, addr, num)
    def read16(self, addr, num=1): return self.readX('rh', 2, addr, num)
    def read32(self, addr, num=1): return self.readX('rw', 4, addr, num)

    def copyX(self, cmd, dest, src, num):
        self.run_command("%s %08x %08x %d" % (cmd, src, dest, num))

    def copy8(self, dest, src, num):  self.copyX('cb', dest, src, num)
    def copy16(self, dest, src, num): self.copyX('ch', dest, src, num)
    def copy32(self, dest, src, num): self.copyX('cw', dest, src, num)

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

    def call(self, addr, a=0, b=0, c=0, d=0):
        self.run_command_noreturn('call %x %d %d %d %d' % (addr, a, b, c, d))

    def call_linux_and_run_microcom(self, addr):
        self.call(addr, 0, 0xffffffff, 0)
        os.system(f'busybox microcom -s 115200 /dev/ttyUSB0')

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

# MAC address
class MAC:
    def __init__(self, a, b, c, d, e, f):
        self.addr = (a, b, c, d, e, f)

    def __repr__(self):
        return '%02x:%02x:%02x:%02x:%02x:%02x' % self.addr

    def __getitem__(self, i):
        return self.addr[i]

    def to_bytes(self):
        return bytes(self.addr)

MAC.broadcast = MAC(0xff,0xff,0xff,0xff,0xff,0xff)

class IP:
    def __init__(self, a, b, c, d):
        self.addr = (a, b, c, d)

    def __repr__(self):
        return '%d.%d.%d.%d' % self.addr

    def __getitem__(self, i):
        return self.addr[i]

    def to_int(self):
        # 10.1.2.3 -> 0x0a010203
        return self.addr[0] << 24 | self.addr[1] << 16 | self.addr[2] <<  8 | self.addr[3]

    def to_bytes(self):
        # IP address in wire format (big endian)
        return bytes(self.addr)

class EMC(Block):
    CAMCMR = 0x00
    CAMCMR_AUP = BIT(0)
    CAMCMR_AMP = BIT(1)
    CAMCMR_ABP = BIT(2)
    CAMCMR_CCAM = BIT(3)
    CAMCMR_ECMP = BIT(4)
    CAMEN = 0x04
    CAMxM = [0x08 + 0x10 * i for i in range(16)]
    CAMxL = [0x0c + 0x10 * i for i in range(16)]
    TXDLSA = 0x88
    RXDLSA = 0x8c
    MCMDR = 0x90
    MCMDR_RXON = BIT(0)
    MCMDR_ALP = BIT(1)
    MCMDR_ARP = BIT(2)
    MCMDR_ACP = BIT(3)
    MCMDR_AEP = BIT(4)
    MCMDR_SPCRC = BIT(5)
    MCMDR_TXON = BIT(8)
    MCMDR_NDEF = BIT(9)
    MCMDR_SDPZ = BIT(16)
    MCMDR_EnSQE = BIT(17)
    MCMDR_FDUP = BIT(18)
    MCMDR_EnMDC = BIT(19)
    MCMDR_OPMOD = BIT(20)
    MCMDR_LBK = BIT(21)
    MCMDR_SWR = BIT(24)
    MIID = 0x94
    MIIDA = 0x98
    FFTCR = 0x9c
    TSDR = 0xa0
    RSDR = 0xa4
    DMARFC = 0xa8
    MIEN = 0xac
    MISTA = 0xb0
    MGSTA = 0xb4
    MPCNT = 0xb8
    MRPC = 0xbc
    MRPCC = 0xc0
    MREPC = 0xc4
    DMARFS = 0xc8
    CTXDSA = 0xcc
    CTXBSA = 0xd0
    CRXDSA = 0xd4
    CRXBSA = 0xd8

    CAMCMR_DEFAULT = CAMCMR_AUP | CAMCMR_ABP | CAMCMR_ECMP
    MCMDR_DEFAULT = MCMDR_OPMOD | MCMDR_EnMDC | MCMDR_FDUP | MCMDR_SPCRC
    MCMDR_ACTIVE = MCMDR_DEFAULT | MCMDR_TXON | MCMDR_RXON

    ARP_BASE = 0xf0000   # start address of ARP frame
    BUFS_BASE = 0x100000 # start address of buffers
    BUF_SIZE = 0x800     # enough for 1 packet and descriptor
    FRAME_SIZE = 0x600   # max. bytes per frame
    BUFS_SIZE = 0x8000   # memory for all buffers per EMC and direction
    MTU = 1420           # max. number of bytes that we'd actually put in a frame

    ETHERTYPE_ARP = 0x806
    ETHERTYPE_IP  = 0x800

    class Buf:
        DATA_OFFSET = 0x200

        def __init__(self, base, lolmon):
            self.base = base
            self.l = lolmon
            self.data_base = self.base + self.DATA_OFFSET
            self.next = self.base # until another address is provided

        def __repr__(self):
            return "%s(0x%x)" % (self.__class__.__name__, self.base)

        def dump(self):
            self.l.dump32(self.base, 4)

    class RXBuf(Buf):
        SL = 0
        BUF_ADDR = 4
        RESERVED = 8
        NEXTDESC = 12

        class Status:
            OWNER_MASK = 0xc0000000
            OWNER_EMC = 0x80000000
            OWNER_ARM = 0x00000000
            MISC_MASK = 0x3fff0000
            LEN_MASK = 0x0000ffff

            def __init__(self, raw):
                self.raw = raw
                self.owner = self.raw & self.OWNER_MASK
                self.misc = self.raw & self.MISC_MASK
                self.len = self.raw & self.LEN_MASK

            def is_ready(self):
                return self.owner == self.OWNER_ARM

            def __repr__(self):
                owner = 'ARM' if self.owner == self.OWNER_ARM else 'EMC'
                return 'RXBuf.Status(%s, 0x%04x, %d)' % (owner, self.misc, self.len)

        def write_initial(self):
            self.l.write32(self.base + self.SL, self.Status.OWNER_EMC)
            self.l.write32(self.base + self.BUF_ADDR, self.data_base)
            self.l.write32(self.base + self.RESERVED, 0)
            self.l.write32(self.base + self.NEXTDESC, self.next)

        def rearm(self):
            self.l.write32(self.base + self.SL, self.Status.OWNER_EMC)
            self.status = None

        def fetch_status(self):
            self.status = self.Status(self.l.read32(self.base + self.SL))

        def fetch_ethertype(self):
            return bswap16(self.l.read16(self.data_base + 12))

        def fetch_data(self):
            return self.l.read8(self.data_base, self.status.len)

        def dump_data(self):
            self.l.dump8(self.data_base, self.status.len)

    class TXBuf(Buf):
        CONTROL = 0
        CONTROL_OWNER_EMC = BIT(31)
        CONTROL_INTEN = BIT(2)
        CONTROL_CRCAPP = BIT(1)
        CONTROL_PADEN = BIT(0)
        BUF_ADDR = 4
        SL = 8
        SL_TXCP = BIT(19)
        NEXTDESC = 12

        CONTROL_GO = CONTROL_OWNER_EMC | CONTROL_CRCAPP | CONTROL_PADEN

        class Status:
            CONTROL_OWNER_EMC = BIT(31)

            def __init__(self, c, sl):
                self.c = c
                self.sl = sl

            def is_ready(self):
                return not(self.c & self.CONTROL_OWNER_EMC)

            def is_good(self):
                return bool(self.sl & SL_TXCP)

        def write_initial(self):
            self.l.write32(self.base + self.CONTROL, 0)
            self.l.write32(self.base + self.BUF_ADDR, self.data_base)
            self.l.write32(self.base + self.SL, 0)
            self.l.write32(self.base + self.NEXTDESC, self.next)

        def fetch_status(self):
            self.status = self.Status(self.l.read32(self.base + self.CONTROL),
                                      self.l.read32(self.base + self.SL))

        def submit(self):
            self.l.write32(self.base + self.SL, self.len)
            self.l.write32(self.base + self.CONTROL, self.CONTROL_GO)

        def set_data(self, data):
            self.len = len(data)
            self.l.write8(self.data_base, list(data))

        def set_data_by_copy(self, addr, length):
            self.len = length
            self.l.copy8(self.data_base, addr, length)

        def dump_data(self):
            self.l.dump8(self.data_base, self.len)

    def set_cam(self, index, mac):
        self.write32(self.CAMxM[index], mac[5] << 24 | mac[4] << 16 | mac[3] << 8 | mac[2])
        self.write32(self.CAMxL[index], mac[1] << 24 | mac[0] << 16)
        self.setclr32(self.CAMEN, index, 1)

    def init(self, buf_base=None):
        if not buf_base:
            if self.base == 0xb0002000:
                buf_base = self.BUFS_BASE
                self.reset = self.clock = 6
                self.mac = MAC(0xaa,0xbb,0xcc,0xdd,0xee,0x01)
                self.ip = IP(10,0,1,1)
            elif self.base == 0xb0003000:
                buf_base = self.BUFS_BASE + 2*self.BUFS_SIZE
                self.reset = self.clock = 7
                self.mac = MAC(0xaa,0xbb,0xcc,0xdd,0xee,0x02)
                self.ip = IP(10,0,1,2)

        # next buffer to use
        self.rx_head = 0
        self.tx_head = 0

        # reset core
        clk.clken(self.clock, 1)
        clk.reset(self.clock, 1)

        # allocate buffers
        self.rx_buf_base = buf_base
        self.tx_buf_base = buf_base + self.BUFS_SIZE
        self.rx_bufs = [self.RXBuf(addr, self.l) for addr in
                range(self.rx_buf_base, self.rx_buf_base + self.BUFS_SIZE, self.BUF_SIZE)]
        self.tx_bufs = [self.TXBuf(addr, self.l) for addr in
                range(self.tx_buf_base, self.tx_buf_base + self.BUFS_SIZE, self.BUF_SIZE)]

        # link them up
        for i, desc in enumerate(self.rx_bufs):
            desc.next = self.rx_bufs[(i + 1) % len(self.rx_bufs)].base
        for i, desc in enumerate(self.tx_bufs):
            desc.next = self.tx_bufs[(i + 1) % len(self.tx_bufs)].base

        # commit buffers to memory
        for desc in self.rx_bufs: desc.write_initial()
        for desc in self.tx_bufs: desc.write_initial()

        # initialize core
        clk.reset(self.clock, 0)
        self.set_cam(0, self.mac)
        # Accept unicast, and broadcast, use CAM
        self.write32(self.CAMCMR, self.CAMCMR_DEFAULT)
        self.write32(self.TXDLSA, self.tx_bufs[0].base)
        self.write32(self.RXDLSA, self.rx_bufs[0].base)
        self.write32(self.DMARFC, self.FRAME_SIZE)
        self.write32(self.MCMDR, self.MCMDR_ACTIVE)

        self.make_arp_packet(self.ARP_BASE)

    def make_arp_packet(self, addr):
        b = b''

        # Ethernet header
        b += MAC.broadcast.to_bytes()
        b += self.mac.to_bytes()
        b += struct.pack('>H', self.ETHERTYPE_ARP)

        # ARP structure
        b += struct.pack('>HHBBH', 1, self.ETHERTYPE_IP, 6, 4, 2)
        b += self.mac.to_bytes() # sender
        b += self.ip.to_bytes()
        b += MAC.broadcast.to_bytes() # target
        b += self.ip.to_bytes()

        # push into memory
        self.l.write8(addr, b)
        self.arp_packet = addr
        self.arp_packet_len = len(b)

    def dump_rx_descs(self):
        for desc in self.rx_bufs: desc.dump()

    def dump_tx_descs(self):
        for desc in self.tx_bufs: desc.dump()

    def advance_rx(self):
        self.rx_head = (self.rx_head + 1) % len(self.rx_bufs)

    def advance_tx(self):
        self.tx_head = (self.tx_head + 1) % len(self.tx_bufs)

    # Get the next RX buffer that is ready, or return None.
    # After use, buf.rearm() must be called.
    def try_get_rx_buf(self):
        self.write32(self.RSDR, 1)
        buf = self.rx_bufs[self.rx_head]
        buf.fetch_status()
        if buf.status.is_ready():
            self.advance_rx()
            return buf

    # Get the next RX buffer that is ready. After use, buf.rearm() must be called.
    def get_rx_buf(self):
        self.write32(self.RSDR, 1)
        buf = self.rx_bufs[self.rx_head]
        while True:
            buf.fetch_status()
            if buf.status.is_ready():
                break
        self.advance_rx()
        return buf

    # receive a frame, as data
    def rx_frame(self):
        buf = self.get_rx_buf()
        data = buf.fetch_data()
        buf.rearm()
        return data

    def dump_frames(self):
        while True:
            buf = self.get_rx_buf()
            buf.dump_data()
            print()
            buf.rearm()

    def get_tx_buf(self):
        buf = self.tx_bufs[self.tx_head]
        while True:
            buf.fetch_status()
            if buf.status.is_ready():
                break
        self.advance_tx()
        return buf

    def submit_tx_buf(self, buf):
        buf.submit()
        self.write32(self.TSDR, 1)

    def tx_frame(self, data):
        buf = self.get_tx_buf()
        buf.set_data(data)
        self.submit_tx_buf(buf)

    def data_chunks(self, data):
        ETH_OVERHEAD = 16
        UDP_OVERHEAD = 28
        TAG_OVERHEAD = 4
        chunk_size = self.MTU - ETH_OVERHEAD - UDP_OVERHEAD
        chunks = (len(data) + chunk_size - 1) // chunk_size
        for i in range(chunks):
            yield i, chunks, data[i*chunk_size : (i + 1)*chunk_size]

    # Reply to an ARP packet. We already know that it's ARP.
    def handle_arp(self, buf):
        data = buf.fetch_data()[14:]

        types = data[0:4]
        op = data[6:8]
        targetip = data[24:28]
        if types == b'\x00\x01\x08\x00' and op == b'\x00\x01' and targetip == self.ip.to_bytes():
            txbuf = self.get_tx_buf()
            txbuf.set_data_by_copy(self.arp_packet, self.arp_packet_len)
            self.submit_tx_buf(txbuf)

    def arp_loop(self):
        while True:
            buf = self.get_rx_buf()
            et = buf.fetch_ethertype()
            print(hex(et))
            if et == self.ETHERTYPE_ARP:
                self.handle_arp(buf)
            buf.rearm()

    def push_data(self, addr, data):
        magic = random.getrandbits(16)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((str(self.ip), 450))
        for i, n, chunk in self.data_chunks(data):
            packet_done = False
            good_tag = struct.pack('>HH', magic, i)
            print(f'\rpacket {i + 1}/{n}...', end='')
            while not packet_done:
                buf = self.try_get_rx_buf()
                if not buf:
                    s.send(good_tag + chunk)  # TODO: retransmit only when necessary
                    continue

                ethertype = bswap16(self.l.read16(buf.data_base + 0xc))
                if ethertype == self.ETHERTYPE_ARP:
                    self.handle_arp(buf)
                if ethertype == self.ETHERTYPE_IP:
                    ip = self.l.read8(buf.data_base + 0x1e, 4)
                    port = bswap16(self.l.read16(buf.data_base + 0x24))
                    tag = self.l.read8(buf.data_base + 0x2a, 4)
                    if ip == self.ip.to_bytes() and port == 450 and tag == good_tag:
                        self.l.copy8(addr, buf.data_base + 0x2e, len(chunk))
                        addr += len(chunk)
                        packet_done = True
                buf.rearm()
        print(' done')

    def push_file(self, addr, filename):
        with open(filename, 'rb') as f:
            data = f.read()
            f.close()
            self.push_data(addr, data)

GCR = MC = USB = KCS = FIU = KCS = GDMA = AES = UART = SMB = PWM = MFT = Block
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

emc0.init()

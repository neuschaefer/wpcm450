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

def get_be16(data, offset):
    return data[offset] << 8 | data[offset+1]

def get_be32(data, offset):
    return get_be16(data, offset) << 16 | get_be16(data, offset+2)

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

    def write_file(self, addr, filename):
        with open(filename, 'rb') as f:
            data = f.read()
            f.close()
            self.write8(addr, data)

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
        emc0.stop() # No DMA please!
        emc1.stop()
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
    CLKDIV    = 0x08
    PLLCON0   = 0x0c
    PLLCON1   = 0x10
    IPSRST    = 0x20

    CLKSEL_CPU_SHIFT    = 0
    CLKSEL_CPU_MASK     = 3
    CLKSEL_USBPHY_SHIFT = 6
    CLKSEL_USBPHY_MASK  = 3
    CLKSEL_UART_SHIFT   = 8
    CLKSEL_UART_MASK    = 3

    CLKDIV_AHB3_SHIFT   = 8
    CLKDIV_AHB3_MASK    = 3
    CLKDIV_UART_SHIFT   = 16
    CLKDIV_UART_MASK    = 15
    CLKDIV_AHB_SHIFT    = 24
    CLKDIV_AHB_MASK     = 3
    CLKDIV_APB_SHIFT    = 26
    CLKDIV_APB_MASK     = 3
    CLKDIV_ADC_SHIFT    = 28
    CLKDIV_ADC_MASK     = 3

    PLLCON_PRST         = BIT(13)
    PLLCON_INDV_SHIFT   = 0
    PLLCON_INDV_MASK    = 0x3f
    PLLCON_OTDV_SHIFT   = 8
    PLLCON_OTDV_MASK    = 0x07
    PLLCON_FBDV_SHIFT   = 16
    PLLCON_FBDV_MASK    = 0x1ff

    def reset(self, line, value):
        self.setclr32(self.IPSRST, line, value)

    def clken(self, line, value):
        self.setclr32(self.CLKEN, line, value)

    def rate_ref(self):
        return 48000000

    def pllcon_to_rate(self, pllcon):
        if pllcon & self.PLLCON_PRST:
            return 0
        indv = (pllcon >> self.PLLCON_INDV_SHIFT) & self.PLLCON_INDV_MASK
        otdv = (pllcon >> self.PLLCON_OTDV_SHIFT) & self.PLLCON_OTDV_MASK
        fbdv = (pllcon >> self.PLLCON_FBDV_SHIFT) & self.PLLCON_FBDV_MASK
        return int(self.rate_ref() / (indv+1) * (fbdv+1) / (otdv+1))

    def rate_pll0(self): return self.pllcon_to_rate(self.read32(self.PLLCON0))
    def rate_pll1(self): return self.pllcon_to_rate(self.read32(self.PLLCON1))

    def rate_select(self, shift):
        sources = [ self.rate_pll0, self.rate_pll1, self.rate_ref ]
        return sources[(self.read32(self.CLKSEL) >> shift) & 3]()

    def rate_cpu(self):    return self.rate_select(self.CLKSEL_CPU_SHIFT) // 2
    def rate_clkout(self): return self.rate_select(self.CLKSEL_CLKOUT_SHIFT)
    def rate_usbphy(self): return self.rate_select(self.CLKSEL_USBPHY_SHIFT)

    def rate_uart(self):
        div = (self.read32(self.CLKDIV) >> self.CLKDIV_UART_SHIFT) & self.CLKDIV_UART_MASK
        return self.rate_select(self.CLKSEL_UART_SHIFT) // (div + 1)

    def div(self, shift):
        div = (self.read32(self.CLKDIV) >> shift) & 3
        return [ 1, 2, 4, 8 ][div]

    def rate_ahb(self):  return self.rate_cpu() // self.div(self.CLKDIV_AHB_SHIFT)
    def rate_ahb3(self): return self.rate_ahb() // self.div(self.CLKDIV_AHB3_SHIFT)
    def rate_apb(self):  return self.rate_ahb() // self.div(self.CLKDIV_APB_SHIFT)
    def rate_adc(self):  return self.rate_ref() // self.div(self.CLKDIV_ADC_SHIFT)

    def set_div(self, shift, div):
        table = { 2**n: n for n in range(4) }
        x = self.read32(self.CLKDIV)
        x &= ~(3 << shift)
        x |= table[div] << shift
        self.write32(self.CLKDIV, x)

    def set_sel(self, shift, parent):
        table = { 'pll0': 0, 'pll1': 1, 'ref': 2 }
        x = self.read32(self.CLKSEL)
        x &= ~(3 << shift)
        x |= table[parent] << shift
        self.write32(self.CLKSEL, x)

    def summary(self):
        print(f'Clock summary:')
        print(f'  REF:      {self.rate_ref()   :10} Hz')
        print(f'  PLL0:     {self.rate_pll0()  :10} Hz')
        print(f'  PLL1:     {self.rate_pll1()  :10} Hz')
        print(f'  CPU:      {self.rate_cpu()   :10} Hz')
        print(f'  USBPHY:   {self.rate_usbphy():10} Hz')
        print(f'  UART:     {self.rate_uart()  :10} Hz')
        print(f'  AHB:      {self.rate_ahb()   :10} Hz')
        print(f'  AHB3:     {self.rate_ahb3()  :10} Hz')
        print(f'  APB:      {self.rate_apb()   :10} Hz')
        print(f'  ADC:      {self.rate_adc()   :10} Hz')

    def make_cpu_slow(self):
        # Copy PLL0 configuration to PLL1, but divide by 2
        pllcon0 = self.read32(self.PLLCON0)
        self.write32(self.PLLCON1, pllcon0 | (1 << self.PLLCON_OTDV_SHIFT))
        print(f"PLL0 at {self.rate_pll0()} Hz, PLL1 at {self.rate_pll1()} Hz")

        # Switch CPU clock to PLL1
        self.set_sel(self.CLKSEL_CPU_SHIFT, 'pll1')
        print(f"AHB3 now at {self.rate_ahb3()}")

    def make_ahb3_fast(self):
        ahb = self.rate_ahb()
        for div in [1, 2, 4, 8]:
            if ahb / div <= 60_000000:
                self.set_div(self.CLKDIV_AHB3_SHIFT, div)
                break
        print(f"AHB3 clock now at {self.rate_ahb3()} Hz")


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
    MIIDA_BUSY = BIT(17)
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
    MTU = 1500           # max. number of bytes that we'd actually put in a frame

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
            RXGD = BIT(20)

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

            def is_good(self):
                return bool(self.raw & self.RXGD)

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

    def stop(self):
        # initiate software reset
        self.write32(self.MCMDR, self.MCMDR_SWR)
        while self.read32(self.MCMDR) & self.MCMDR_SWR:
            pass

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
        while True:
            buf = self.try_get_rx_buf()
            if buf:
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
        ETH_OVERHEAD = 14
        UDP_OVERHEAD = 28
        TAG_OVERHEAD = 4
        chunk_size = self.MTU - ETH_OVERHEAD - UDP_OVERHEAD - TAG_OVERHEAD
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
            s.send(good_tag + chunk)
            while not packet_done:
                buf = self.try_get_rx_buf()
                if not buf:
                    # retransmit only when necessary
                    s.send(good_tag + chunk)
                    continue
                if not buf.status.is_good():
                    buf.rearm()
                    continue

                header = self.l.read8(buf.data_base, 0x30)
                ethertype = get_be16(header, 0xc)
                if ethertype == self.ETHERTYPE_ARP:
                    self.handle_arp(buf)
                if ethertype == self.ETHERTYPE_IP:
                    ip = get_be32(header, 0x1e)
                    port = get_be16(header, 0x24)
                    tag = header[0x2a:0x2e]
                    if ip == self.ip.to_int() and port == 450 and tag == good_tag:
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

    def get_mdccr(self):
        return (self.read32(self.MIIDA) >> 20) & 0xf

    def set_mdccr(self, value):
        miida = self.read32(emc0.MIIDA) & ~(0xf << 20)
        self.write32(self.MIIDA, miida | (value << 20))

    def mdio_do(self, phy, reg, write):
        assert phy in range(0x20)
        assert reg in range(0x20)
        write = int(bool(write))
        miida = self.read32(self.MIIDA) & ~0xffff
        miida |= self.MIIDA_BUSY | write << 16 | phy << 8 | reg
        self.write32(self.MIIDA, miida)
        timeout = time.monotonic() + 0.1
        while self.read32(self.MIIDA) & self.MIIDA_BUSY:
            if time.monotonic() >= timeout:
                print("MDIO transfer timed out")
                break

    def mdio_read(self, phy, reg):
        self.mdio_do(phy, reg, False)
        return self.read32(self.MIID)

    def mdio_write(self, phy, reg, value):
        self.write32(self.MIID, value)
        self.mdio_do(phy, reg, True)

    def mdio_scan(self):
        for phy in range(0x20):
            hi = self.mdio_read(phy, 2)
            lo = self.mdio_read(phy, 3)
            if hi != 0xffff:
                print('MDIO @ %d, device %04x:%04x' % (phy, hi, lo))


class GCR(Block):
    PDID = 0
    PWRON = 4
    MFSEL1 = 0xc
    MFSEL2 = 0x10

class FIU(Block):
    FIU_CFG = 0
    BURST_CFG = 1
    RESP_CFG = 2
    CFBB_PROT = 3
    FWIN1_LOW = 4
    FWIN1_HIGH = 6
    FWIN2_LOW = 8
    FWIN2_HIGH = 0xa
    FWIN3_LOW = 0xc
    FWIN3_HIGH = 0xe
    FWIN_LOW = { 1: FWIN1_LOW, 2: FWIN2_LOW, 3: FWIN3_LOW }
    FWIN_HIGH = { 1: FWIN1_HIGH, 2: FWIN2_HIGH, 3: FWIN3_HIGH }
    PROT_LOCK = 0x10
    PROT_CLEAR = 0x11
    SPI_FL_CFG = 0x14
    SPI_TIM = 0x15
    UMA_CODE = 0x16
    UMA_AB0 = 0x17
    UMA_AB1 = 0x18
    UMA_AB2 = 0x19
    UMA_DB0 = 0x1a
    UMA_DB1 = 0x1b
    UMA_DB2 = 0x1c
    UMA_DB3 = 0x1d
    UMA_CTS = 0x1e
    CTS_EXEC_DONE = BIT(7)
    CTS_DEV_NUM_SHIFT = 5
    CTS_RD_WR = BIT(4)
    CTS_A_SIZE = BIT(3)
    CTS_D_SIZE_SHIFT = 0
    UMA_ECTS = 0x1f

    MMFLASH_BASE = 0xc0000000

    def __init__(self, lolmon, base=None):
        super().__init__(lolmon, base)
        self.cs = 0

    def dump(self):
        self.l.dump8(self.base, 0x20)

    def get_fwin(self, i):
        return self.read16(self.FWIN_LOW[i]) * 0x1000, self.read16(self.FWIN_HIGH[i]) * 0x1000

    def any_fwin_contains(self, x):
        return any([x in range(*fiu.get_fwin(i)) for i in [1, 2, 3]])

    def set_fwin(self, i, low, high):
        self.write16(self.FWIN_LOW[i], low // 0x1000)
        self.write16(self.FWIN_HIGH[i], high // 0x1000)

    def get_uma_code(self):
        return self.read8(self.UMA_CODE)

    def set_uma_code(self, code):
        self.write8(self.UMA_CODE, code)

    def get_uma_addr(self):
        a  = self.read8(self.UMA_AB0)
        a |= self.read8(self.UMA_AB1) <<  8
        a |= self.read8(self.UMA_AB2) << 16
        return a

    def set_uma_addr(self, a):
        self.write8(self.UMA_AB0, a & 0xff)
        self.write8(self.UMA_AB1, (a >> 8) & 0xff)
        self.write8(self.UMA_AB2, (a >> 16) & 0xff)

    def get_uma_data(self):
        return [self.read8(self.UMA_DB0),
                self.read8(self.UMA_DB1),
                self.read8(self.UMA_DB2),
                self.read8(self.UMA_DB3)]

    def do_uma(self, write, use_addr, data_len):
        cts = self.CTS_EXEC_DONE | (self.cs << self.CTS_DEV_NUM_SHIFT) | (data_len << self.CTS_D_SIZE_SHIFT)
        if use_addr:
            cts |= self.CTS_A_SIZE
        if write:
            cts |= self.CTS_RD_WR
        self.write8(self.UMA_CTS, cts)
        while self.read8(self.UMA_CTS) & self.CTS_EXEC_DONE:
            print('lol')

    # Read chip ID
    def rdid(self):
        self.set_uma_code(0x9f)
        self.do_uma(False, False, 3)
        return self.get_uma_data()[:3]

    # Read status register
    def rsr(self):
        self.set_uma_code(0x05)
        self.do_uma(False, False, 1)
        return self.get_uma_data()[0]

    # Write Enable
    def wren(self):
        self.set_uma_code(0x06)
        self.do_uma(False, False, 0)

    # Sector Erase
    def erase4k(self, addr, cs=0):
        self.wren()
        self.set_uma_code(0x20)
        self.set_uma_addr(addr)
        self.do_uma(False, True, 0)

        # Poll until the erase is done.
        #   On Winbond: RSR-1.BUSY
        #   On Macronix: SR.WIP
        while self.rsr() & 0x01:
            pass

    # program at 8-bit width
    def prog8(self, addr, data):
        addr = addr & 0xffffff
        if isinstance(data, list) or isinstance(data, bytes):
            for i, d in enumerate(data):
                self.prog8(addr+i, d)
        else:
            assert self.any_fwin_contains(addr)
            print("prog %06x = %2x" % (addr, data))
            self.wren()
            self.l.write8(addr | self.MMFLASH_BASE, data)

    def prog8_as_needed(self, addr, data):
        addr = addr & 0xffffff
        fdata = self.mm_read(len(data))
        for i in range(len(data)):
            if fdata[i] != data[i]:
                self.prog8(addr+i, data[i])

    # If the flash has any bits cleared that are set in the new data, we need
    # an erase to set these bits again.
    def page_needs_erase(self, addr, data):
        addr = addr & 0xffffff
        assert addr & 0xfff == 0
        assert len(data) <= 0x1000
        fdata = self.mm_read(len(data))
        for i in range(len(data)):
            if ~fdata[i] & data[i]:
                return True
        return False

    # erase/reprogram a page or more as needed
    def flash(self, addr, data):
        addr = addr & 0xffffff
        assert addr & 0xfff == 0
        for p in range(0, len(data), 0x1000):
            pdata = data[p:p+0x1000]
            if self.page_needs_erase(addr+p, pdata):
                self.erase4k(addr+p)
            self.prog8_as_needed(addr+p, pdata)

    def mm_read(self, addr, data_len):
        addr = addr & 0xffffff
        return self.l.read8(addr | self.MMFLASH_BASE, data_len)

    def mm_dump(self, addr, data_len):
        addr = addr & 0xffffff
        return self.l.dump8(addr | self.MMFLASH_BASE, data_len)

    # perform READ using UMA
    def uma_read(self, addr, data_len=4):
        self.set_uma_code(0x03)
        self.set_uma_addr(addr)
        self.do_uma(False, True, data_len)
        return self.get_uma_data()

    # perform FAST READ using UMA. FIU automatically inserts the dummy byte
    def uma_fast_read(self, addr, data_len=4):
        self.set_uma_code(0x0b)
        self.set_uma_addr(addr)
        self.do_uma(False, True, data_len)
        return self.get_uma_data()

    def uma_assert(self):
        x = self.read8(self.UMA_ECTS)
        x &= ~BIT(self.cs)
        self.write8(self.UMA_ECTS, x)

    def uma_deassert(self):
        x = self.read8(self.UMA_ECTS)
        x |= BIT(self.cs)
        self.write8(self.UMA_ECTS, x)

    def hello_la(self):
        # Pulse the CS# line to give my logic analyzer a chance to listen up
        self.uma_assert()
        self.uma_deassert()

    def set_read_burst(self, burst):
        table = { 1: 0, 16: 3 }
        x = self.read8(self.BURST_CFG)
        x &= ~3
        x |= table[burst]
        self.write8(self.BURST_CFG, x)

    def safe_uma(self, code, write, use_addr, data_len):
        # let the SPI flash think this is a read
        self.uma_assert()
        self.set_uma_code(0x03)
        self.do_uma(False, False, 0)

        # now for the main act
        self.set_uma_code(code)
        self.do_uma(write, use_addr, data_len)

        # the end
        self.uma_deassert()

    def uma_dummy_test(self):
        # The pattern:
        # (R) C
        # (W) C
        # (R) C A
        # (W) C A
        # (R) C D D D D
        # (W) C D D D D
        # (R) C A D D D D
        # (W) C A D D D D
        for code in [0x03, 0x0b]:
            for data_len in [0, 4]:
                for use_addr in [0, 1]:
                    for write in [0, 1]:
                        self.set_uma_addr(0x112233)
                        self.safe_uma(code, write, use_addr, data_len)


MC = USB = KCS = GDMA = AES = UART = SMB = PWM = MFT = Block
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

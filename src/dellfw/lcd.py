#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
#
# Analysis of SSPI command logs
import re, sys

re_sspi = re.compile('^\[.*\] SSPI.WR[A-Z]* ([01]), .*\[([0-9]*),([0-9]*)\] *([0-9a-f ]*) -> ([0-9a-f ]*)$')

def parse_hex(h):
    h = h.strip()
    if h == '':
        return b''
    return bytes([int(x, 16) for x in h.strip().split(' ')])

last_row = 0
matrix = {}

def render():
    if 0 not in matrix:
        return

    print(' ' + '-' * len(matrix[0]))
    for row in matrix:
        data = matrix[row]
        if data == b'\0' * len(data):
            continue

        for i in range(8):
            line = ''
            for byte in data:
                if byte & (1 << i):
                    line += 'o'
                else:
                    line += ' '
            print(line)



def crunch(fn):
    f = open(fn, 'r')

    for line in f.readlines():
        m = re_sspi.match(line)
        if not m:
            continue

        cs = int(m.group(1))
        send_len = int(m.group(2))
        recv_len = int(m.group(3))
        send_data = parse_hex(m.group(4))
        recv_data = parse_hex(m.group(5))

        assert len(send_data) == send_len
        assert len(recv_data) == recv_len

        if cs == 0 and send_len == 4:
            assert send_data[0] == 0x46
            assert send_data[1] in range(0xb0, 0xbf)
            last_row = send_data[1] - 0xb0

        if cs == 1:
            matrix[last_row] = send_data
            render()


if len(sys.argv) == 2:
    crunch(sys.argv[1])
else:
    print("Usage: lcd.py trace.log")

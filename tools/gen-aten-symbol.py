#!/usr/bin/python3
# SPDX-License-Identifier: MIT
import argparse

parser = argparse.ArgumentParser(description='generate a flash page with the ATEN symbol in it')
parser.add_argument('filename')

args = parser.parse_args()


buf = bytearray(0x10000)

for i in range(0x10000):
    buf[i] = 0xff

buf[0xffb3:0xffb3+8] = b'ATENs_FW'


f = open(args.filename, 'wb')
f.write(buf)
f.close()

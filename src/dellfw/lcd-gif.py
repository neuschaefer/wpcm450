#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
#
# Turn LCD commands in trace logs into an animated GIF
import re, sys
from PIL import Image, ImageDraw

re_sspi = re.compile('^\[.*\] SSPI.WR[A-Z]* ([01]), .*\[([0-9]*),([0-9]*)\] *([0-9a-f ]*) -> ([0-9a-f ]*)$')

def parse_hex(h):
    h = h.strip()
    if h == '':
        return b''
    return bytes([int(x, 16) for x in h.strip().split(' ')])

last_row = 0
matrix = {}

frame_log = []
interesting_rows = set()
max_width = 0

def save_frame():
    if 0 not in matrix:
        return

    for row in matrix:
        data = matrix[row]
        if data != b'\0' * len(data):
            interesting_rows.add(row)
            global max_width
            if len(data) > max_width:
                max_width = len(data)
            frame_log.append(matrix.copy())


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
            save_frame()

def write_gif(fn):
    rows = list(interesting_rows)
    height = len(rows) * 8
    width = max_width

    frames = []
    for matrix in frame_log:
        im = Image.new('RGB', (width, height), "blue")
        px = im.load()

        for ri, row in enumerate(rows):
            data = matrix[row]
            for i in range(len(data)):
                for j in range(8):
                    if (1 << j) & data[i]:
                        px[i, 8*ri+j] = 0xffffff

        frames.append(im)

    if frames == []:
        print("No image data found!")
    else:
        frames[0].save(fn, format="GIF", append_images=frames, save_all=True, duration=10, loop=0)
        print(len(frames), "frames saved.")

if len(sys.argv) == 3:
    crunch(sys.argv[1])
    write_gif(sys.argv[2])
else:
    print("Usage: lcd.py trace.log lcd.gif")

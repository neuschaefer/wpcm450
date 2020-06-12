# SPDX-License-Identifier: MIT

CROSS_COMPILE := arm-linux-gnueabi-
OBJCOPY := $(CROSS_COMPILE)objcopy
AS := $(CROSS_COMPILE)as
CC := $(CROSS_COMPILE)gcc
LD := $(CROSS_COMPILE)ld
ASFLAGS :=
MKIMAGE := ../tools/mkimage

all: scream.bin scream.img


%.o: %.s
	$(AS) $< -o $@

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@

scream.img: scream.bin
	$(MKIMAGE) -x -b 0x40B80000 -e 0x40B80000 -n scream -u 9 -i $< -o $@

scream.elf: scream.o
	$(LD) $(LDFLAGS) scream.o -o $@


clean:
	rm -f *.o scream.elf scream.bin

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
	$(MKIMAGE) -acx -b 0x40e00000 -l 0x8000 -e 0x8000 -n scream -u 7 -i $< -o $@

scream.elf: scream.o
	$(LD) $(LDFLAGS) scream.o -o $@


clean:
	rm -f *.o scream.elf scream.bin scream.img

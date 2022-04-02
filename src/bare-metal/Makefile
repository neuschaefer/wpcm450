# SPDX-License-Identifier: MIT

CROSS_COMPILE := arm-linux-gnueabi-
OBJCOPY := $(CROSS_COMPILE)objcopy
AS := $(CROSS_COMPILE)as
CC := $(CROSS_COMPILE)gcc
LD := $(CROSS_COMPILE)ld
ASFLAGS :=
MKIMAGE := ../../tools/mkimage
LOLCONV := ../../tools/lolconv
CFLAGS  := -Os -fno-builtin -nostdlib -Wall -Wno-unused-function -Wno-main
LDFLAGS := -T monitor.ld

all: scream.img monitor.img tlbtest.lol getuartdiv.lol monitor-flash.bin \
	monitor-flash-16m.bin monitor-flash-32m.bin


%.o: %.s
	$(AS) $< -o $@

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@

%.lol: %.bin
	$(LOLCONV) 0x10000 $< > $@
	cat $@

%.elf: %.o
	$(LD) $(LDFLAGS) $< -o $@

bootscript.elf: bootscript.txt
	cp bootscript.txt bootscript.tmp
	printf '\0' >> bootscript.tmp
	$(OBJCOPY) -I binary -O elf32-littlearm -B armv5t --rename-section .data=.bootscript bootscript.tmp $@
	rm bootscript.tmp

bootscript.txt: bootscript.txt.default
	cp $+ $@

MONITOR_OBJS = start.o monitor.o bootscript.elf
monitor.elf: $(MONITOR_OBJS) monitor.ld
	$(LD) $(LDFLAGS) $(MONITOR_OBJS) -o $@

scream.img: scream.bin
	$(MKIMAGE) -acx -b 0x40b00000 -l 0x8000 -e 0x8000 -n scream -u 6 -i $< -o $@

monitor.img: monitor.bin
	$(MKIMAGE) -acx -b 0x40b00000 -l 0x6400000 -e 0x6400000 -n monitor -u 6 -i $< -o $@

monitor-flash.bin: monitor.bin
	(printf 'P\004U\252'; cat $+) > $@

monitor-flash-16m.bin: monitor-flash.bin
	cp $+ $@
	truncate -s 16M $@

monitor-flash-32m.bin: monitor-flash.bin
	cp $+ $@
	truncate -s 32M $@

clean:
	rm -f *.o scream.elf scream.bin scream.img \
	          monitor.elf monitor.bin monitor.img bootscript.elf bootscript.tmp \
		  monitor-flash.bin monitor-flash-16m.bin monitor-flash-32m.bin

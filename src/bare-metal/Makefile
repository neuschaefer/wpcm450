# SPDX-License-Identifier: MIT
# Copyright (C) J. Neuschäfer

CROSS_COMPILE := arm-linux-gnueabi-
OBJCOPY := $(CROSS_COMPILE)objcopy
AS := $(CROSS_COMPILE)as
CC := $(CROSS_COMPILE)gcc
LD := $(CROSS_COMPILE)ld
ASFLAGS :=
LOLCONV := ../../tools/lolconv
CFLAGS  := -Os -fno-builtin -nostdlib -Wall -Wno-unused-function -Wno-main -ggdb
LDFLAGS := -T monitor.ld

all: tlbtest.lol getuartdiv.lol monitor-flash.bin \
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

monitor-flash.bin: monitor.bin
	(printf 'P\004U\252'; cat $+) > $@

monitor-flash-16m.bin: monitor-flash.bin
	cp $+ $@
	truncate -s 16M $@

monitor-flash-32m.bin: monitor-flash.bin
	cp $+ $@
	truncate -s 32M $@

clean:
	rm -f *.o scream.elf scream.bin \
	          monitor.elf monitor.bin bootscript.elf bootscript.tmp \
		  monitor-flash.bin monitor-flash-16m.bin monitor-flash-32m.bin

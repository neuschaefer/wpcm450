# SPDX-License-Identifier: MIT
# Copyright (C) J. Neuschäfer

CROSS_COMPILE := arm-linux-gnueabi-
OBJCOPY := $(CROSS_COMPILE)objcopy
AS := $(CROSS_COMPILE)as
CC := $(CROSS_COMPILE)gcc
LD := $(CROSS_COMPILE)ld
CFLAGS := -Wall -static -Os

PROGRAMS = memscan memdump gpiodump power

all: $(PROGRAMS)

clean:
	rm -f $(PROGRAMS)

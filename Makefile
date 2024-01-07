# SPDX-License-Identifier: MIT
# Copyright (C) J. Neuschäfer

src:
	+$(MAKE) -C src/bare-metal
	+$(MAKE) -C src/linux
	+$(MAKE) -C src/dellfw

clean:
	+$(MAKE) -C src clean

lint:
	reuse lint

.PHONY: src clean

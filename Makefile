src: tools
	+$(MAKE) -C src/bare-metal
	+$(MAKE) -C src/linux

tools:
	+$(MAKE) -C tools

clean:
	+$(MAKE) -C src clean
	+$(MAKE) -C tools clean

.PHONY: src tools clean

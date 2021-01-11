src: tools
	+$(MAKE) -C src/bare-metal

tools:
	+$(MAKE) -C tools

clean:
	+$(MAKE) -C src clean
	+$(MAKE) -C tools clean

.PHONY: src tools clean

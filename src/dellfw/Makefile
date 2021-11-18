.PHONY: clean uuencode

trace.so: trace.c
	$(CC) -O2 -Wall -shared -fPIC $+ -ldl -o $@

uuencode: trace.so
	gzip < $+ | uuencode $+.gz

clean:
	rm -f trace.so*

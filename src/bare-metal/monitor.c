/* SPDX-License-Identifier: MIT */

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#define ARRAY_LENGTH(a) (sizeof(a) / sizeof((a)[0]))

/* MMIO accessors */

static uint8_t  read8(unsigned long addr)  { return *(volatile uint8_t *)addr; }
static uint16_t read16(unsigned long addr) { return *(volatile uint16_t *)addr; }
static uint32_t read32(unsigned long addr) { return *(volatile uint32_t *)addr; }

static void write8(unsigned long addr, uint8_t value)   { *(volatile uint8_t *)addr = value; }
static void write16(unsigned long addr, uint16_t value) { *(volatile uint16_t *)addr = value; }
static void write32(unsigned long addr, uint32_t value) { *(volatile uint32_t *)addr = value; }


/* UART driver */

#define UART_BASE 0xb8000000

static int uart_can_tx(void)
{
	return !!(read32(UART_BASE + 0x14) & 0x20);
}

static int uart_can_rx(void)
{
	return !!(read32(UART_BASE + 0x14) & 1);
}

static void uart_tx(char ch)
{
	while (!uart_can_tx())
		;
	write32(UART_BASE + 0, ch);
}

static char uart_rx(void)
{
	while (!uart_can_rx())
		;
	return read32(UART_BASE + 0);
}

#define MFSEL1 0xb000000c
static void uart_init(void)
{
	/* Set MFSEL1.BSPSEL to enable UART0 pinmux */
	uint32_t mfsel1 = read32(MFSEL1);
	write32(MFSEL1, mfsel1 | (1 << 9));

	/*
	 * Set divisor to 13 (24MHz / 16 / 13 = 115384Hz. Close enough.)
	 * The -2 is a Nuvoton-specific quirk.
	 */
	write32(UART_BASE + 0x0c, 0x80);   // enable divisor latch
	write32(UART_BASE + 0x00, 13 - 2); // low byte
	write32(UART_BASE + 0x04, 0);      // high byte
	write32(UART_BASE + 0x0c, 0x03);   // disable divisor latch; set 8n1
}


/* Timer driver */

#define TIMER_BASE	0xb8001000
#define TCSR0		(TIMER_BASE + 0x00)
#define TICR0		(TIMER_BASE + 0x08)
#define TDR0		(TIMER_BASE + 0x10)
#define WTCR		(TIMER_BASE + 0x1c)

static bool timer_is_active()
{
	return !!(read32(TCSR0) & (1 << 25));
}

static void start_timer(uint32_t usecs)
{
	/* Reset timer 0 */
	write32(TCSR0, 1 << 26);

	/* Set initial count */
	write32(TICR0, usecs / 10);

	/*
	 * Assuming the input clock runs at 24 MHz, set the prescaler to 240 to
	 * let the timer decrement at 0.1 MHz.
	 */
	uint32_t tcsr = 240 - 1;

	/* Enable */
	tcsr |= 1 << 30;

	write32(TCSR0, tcsr);

	/* Wait for the timer to become active */
	while (!timer_is_active())
		;
}

static bool timeout()
{
	/* Timeout is reached when the timer is not active anymore */
	return !timer_is_active();
}

static void watchdog_reset()
{
	write32(WTCR, 0x82);
}


/* Console I/O functions */

/* Print one character. LF is converted to CRLF. */
static int putchar(int c)
{
	if (c == '\n')
		uart_tx('\r');
	uart_tx(c);
	return c;
}

/* Print a string. */
static void putstr(const char *s)
{
	for (const char *p = s; *p; p++)
		putchar(*p);
}

/* Print a line. CRLF is added at the end. */
static int puts(const char *s)
{
	putstr(s);
	putchar('\n');
	return 0;
}

/* Print a 8-bit number in hex. */
static void put_hex8(uint8_t x)
{
	static const char hex[16] = "0123456789abcdef";

	putchar(hex[x >> 4]);
	putchar(hex[x & 15]);
}

/* Print a 16-bit number in hex. */
static void put_hex16(uint16_t x)
{
	put_hex8(x >> 8);
	put_hex8(x & 255);
}

/* Print a 32-bit number in hex. */
static void put_hex32(uint32_t x)
{
	put_hex16(x >> 16);
	put_hex16(x & 65535);
}

/* Get a character from the UART */
static int getchar(void)
{
	return uart_rx();
}


/* String functions */

static size_t strlen(const char *s)
{
	size_t len = 0;

	for (const char *p = s; *p; p++)
		len++;

	return len;
}

static int strncmp(const char *a, const char *b, size_t n)
{
	for (size_t i = 0; i < n && a[i] && b[i]; i++) {
		if (a[i] != b[i])
			return (int)a[i] - (int)b[i];
	}

	return 0;
}

static void *memcpy(void *d, const void *s, size_t n)
{
	char *dc = d;
	const char *sc = s;

	for (size_t i = 0; i < n; i++)
		dc[i] = sc[i];

	return d;
}

/* Parse a number, similar to strtol. base 0 means auto-detect */
static bool parse_int(const char *s, uint32_t base, uint32_t *result)
{
	uint32_t x = 0, digit;
	const char *p = s;

	if (base == 0) {
		if (s[0] == '0' && s[1] == 'x') {
			base = 16;
			p += 2;
		} else {
			base = 10;
		}
	}

	for (; *p; p++) {
		if (*p >= '0' && *p <= '9') {
			digit = *p - '0';
		} else if (*p >= 'a' && *p <= 'z') {
			digit = *p - 'a' + 10;
		} else if (*p >= 'A' && *p <= 'Z') {
			digit = *p - 'A' + 10;
		} else {
			putstr("Invalid number ");
			puts(s);
			return false;
		}

		if (digit >= base) {
			putstr("Invalid number ");
			puts(s);
			return false;
		}

		x *= base;
		x += digit;
	}

	*result = x;
	return true;
}


/* Command interpreter */

struct command {
	/* The name of the command, null-terminated if possible */
	char name[4];

	/* A description of the arguments */
	const char *arguments;

	/* A description of the function */
	const char *description;

	/* The implementation */
	void (*function)(int argc, char **argv);
};

static void cmd_echo(int argc, char **argv)
{
	for (int i = 1; i < argc; i++) {
		putstr(argv[i]);
		putchar(' ');
	}
	putchar('\n');
}

static void cmd_read(int argc, char **argv)
{
	size_t elems_per_line, increment, elems, addr, pos = 0;
	char op = argv[0][1];

	switch (argc) {
	case 2:
		elems = 1;
		break;
	case 3:
		if (!parse_int(argv[2], 0, &elems))
			return;
		break;
	default:
		puts("Usage error");
		return;
	}

	switch (op) {
	case 'b':
		elems_per_line = 16;
		increment = 1;
		break;
	case 'h':
		elems_per_line = 16;
		increment = 2;
		break;
	case 'w':
		elems_per_line = 8;
		increment = 4;
		break;
	default:
		return;
	}

	if (!parse_int(argv[1], 16, &addr))
		return;

	for (size_t i = 0; i < elems; i++) {
		uint32_t value;

		/* Beginning of the line */
		if (pos == 0) {
			if (i)
				putchar('\n');
			put_hex32(addr);
			putstr(": ");
		} else {
			putchar(' ');
		}

		switch (op) {
		case 'b':
			value = read8(addr);
			put_hex8(value);
			break;
		case 'h':
			value = read16(addr);
			put_hex16(value);
			break;
		case 'w':
			value = read32(addr);
			put_hex32(value);
			break;
		}

		addr += increment;
		if (++pos == elems_per_line)
			pos = 0;
	}

	putchar('\n');
}

static void cmd_write(int argc, char **argv)
{
	size_t increment, addr;
	char op = argv[0][1];

	if (argc < 3) {
		puts("Usage error");
		return;
	}

	switch (op) {
	case 'b':
		increment = 1;
		break;
	case 'h':
		increment = 2;
		break;
	case 'w':
		increment = 4;
		break;
	default:
		return;
	}

	if (!parse_int(argv[1], 16, &addr))
		return;

	for (size_t i = 2; i < argc; i++) {
		uint32_t value;

		if (!parse_int(argv[i], 0, &value))
			return;

		switch (op) {
		case 'b':
			write8(addr, value);
			break;
		case 'h':
			write16(addr, value);
			break;
		case 'w':
			write32(addr, value);
			break;
		}

		addr += increment;
	}
}

static void cmd_copy(int argc, char **argv)
{
	size_t increment, src, dest, count;
	char op = argv[0][1];

	if (argc < 3) {
		puts("Usage error");
		return;
	}

	switch (op) {
	case 'b':
		increment = 1;
		break;
	case 'h':
		increment = 2;
		break;
	case 'w':
		increment = 4;
		break;
	default:
		return;
	}

	if (!parse_int(argv[1], 16, &src))
		return;
	if (!parse_int(argv[2], 16, &dest))
		return;
	if (!parse_int(argv[3], 0, &count))
		return;

	for (size_t i = 0; i < count; i++) {
		uint32_t value;

		switch (op) {
		case 'b':
			value = read8(src);
			write8(dest, value);
			break;
		case 'h':
			value = read16(src);
			write16(dest, value);
			break;
		case 'w':
			value = read32(src);
			write32(dest, value);
			break;
		}

		src  += increment;
		dest += increment;
	}
}

void instruction_memory_barrier(void);
static void cmd_imb(int argc, char **argv)
{
	instruction_memory_barrier();
}

void do_call(uint32_t fn, uint32_t a1, uint32_t a2, uint32_t a3);
static void cmd_call(int argc, char **argv)
{
	uint32_t fn, args[3];
	int i;

	if (argc < 2) {
		puts("Usage error");
		return;
	}

	if (!parse_int(argv[1], 16, &fn))
		return;

	for (i = 0; i < 3 && 2 + i < argc; i++) {
		args[i] = 0;
		if (2 + i < argc)
			parse_int(argv[2 + i], 0, &args[i]);
	}

	instruction_memory_barrier();

	do_call(fn, args[0], args[1], args[2]);
}

static void source(const char *script);
static void cmd_src(int argc, char **argv)
{
	uint32_t script;

	if (argc != 2) {
		puts("Usage error");
		return;
	}

	if (!parse_int(argv[1], 16, &script))
		return;

	source((const char *)script);
}

static void cmd_reset(int argc, char **argv)
{
	if (argc != 1) {
		puts("Usage error");
		return;
	}

	watchdog_reset();
}

extern const char _bootscript[];
static void cmd_boot(int argc, char **argv)
{
	if (argc != 1) {
		puts("Usage error");
		return;
	}

	source(_bootscript);
}

static void cmd_help(int argc, char **argv);
static const struct command commands[] = {
	{ "help", "[command]", "Show help output for one or all commands", cmd_help },
	{ "echo", "[words]", "Echo a few words", cmd_echo },
	{ "rb", "address [count]", "Read one or more bytes", cmd_read },
	{ "rh", "address [count]", "Read one or more half-words (16-bit)", cmd_read },
	{ "rw", "address [count]", "Read one or more words (32-bit)", cmd_read },
	{ "wb", "address values", "Write one or more bytes", cmd_write },
	{ "wh", "address values", "Write one or more half-words (16-bit)", cmd_write },
	{ "ww", "address values", "Write one or more words (32-bit)", cmd_write },
	{ "cb", "source destination count", "Copy one or more bytes", cmd_copy },
	{ "ch", "source destination count", "Copy one or more half-words (16-bit)", cmd_copy },
	{ "cw", "source destination count", "Copy one or more words (32-bit)", cmd_copy },
	{ "imb", "", "Instruction memory barrier", cmd_imb },
	{ "call", "address [up to 3 args]", "Call a function by address", cmd_call },
	{ "src", "address", "Source/run script at address", cmd_src },
	{ "rst", "", "Perform a system reset", cmd_reset },
	{ "boot", "", "Continue with the usual boot flow", cmd_boot },
};

static const struct command *find_command(const char *name)
{
	if (strlen(name) > 4)
		return NULL;

	for (int i = 0; i < ARRAY_LENGTH(commands); i++)
		if (!strncmp(name, commands[i].name, 4))
			return &commands[i];

	return NULL;
}

static void cmd_help(int argc, char **argv)
{
	if (argc > 1) {
		for (int i = 1; i < argc; i++) {
			const char *name = argv[i];

			const struct command *cmd = find_command(name);
			if (!cmd) {
				putstr("Unknown command ");
				puts(name);
				return;
			}

			putstr(name);
			putstr(" - ");
			puts(cmd->description);

			putstr("Usage: ");
			putstr(name);
			putchar(' ');
			puts(cmd->arguments);
		}
	} else {
		for (int i = 0; i < ARRAY_LENGTH(commands); i++) {
			char name[5];

			memcpy(name, commands[i].name, 4);
			name[4] = 0;

			putstr(name);
			putstr(" - ");
			puts(commands[i].description);
		}
	}
}


/* Main program */

/* Read a line from the UART, providing some basic line editing. Ensure NUL-termination */
static void edit_line(char *line, size_t size)
{
	size_t cursor = 0;

beginning:
	putstr("> ");
	for (size_t i = 0; i < cursor; i++)
		putchar(line[i]);

	while (true) {
		char c = getchar();

		switch ((uint8_t)c) {
		case 0x08: /* backspace */
		case 0x7f:
			if (cursor) {
				cursor--;
				putstr("\10 \10");
			}
			break;

		case 0x15: /* ^U, NAK: Delete the current input */
			while (cursor) {
				cursor--;
				putstr("\10 \10");
			}
			break;

		case 0x0c: /* ^L: form feed, clear screen */
			putstr("\033[H\033[J");
			goto beginning;

		case '\n': /* newline/enter */
		case '\r':
			line[cursor] = 0;
			putchar('\n');
			return;

		default:
			/* Ignore all ASCII control characters not handled above */
			if (c < 0x20)
				break;

			/* Just normal characters */
			if (cursor < size - 1) {
				line[cursor] = c;
				cursor++;
				putchar(c);
			}
			break;
		}
	}
}

static size_t tokenize_line(char *line, char **argv, size_t argv_length)
{
	enum { IDLE, WORD } state = IDLE;
	size_t argv_index = 0;
	char *word_start = NULL;

	for (char *p = line; *p && argv_index < argv_length; p++) {
		char c = *p;

		/* Find the beginning of a comment, ignore all word after */
		if(c == '#')
			break;

		switch (state) {
		case IDLE:
			/* Find the beginning of a word */
			if (c != ' ') {
				word_start = p;
				state = WORD;
			}
			break;
		case WORD:
			/* Find the end of a word */
			if (c == ' ' || c == '\0') {
				*p = 0;
				state = IDLE;
				argv[argv_index++] = word_start;
				word_start = NULL;
			}
			break;
		}
	}

	if (word_start && argv_index < argv_length)
		argv[argv_index++] = word_start;

	return argv_index;
}

static void execute_line(char *line)
{
	char *argv[16];
	int argc;
	const struct command *cmd;

	argc = tokenize_line(line, argv, ARRAY_LENGTH(argv));
	if (argc == 0)
		return;

	cmd = find_command(argv[0]);
	if (!cmd) {
		putstr("Unknown command ");
		puts(argv[0]);
		return;
	}

	cmd->function(argc, argv);
}

static void source(const char *script)
{
	char line[128];
	const char *p;
	int pos = 0;

	for (p = script; *p; p++) {
		switch (*p) {
		case '\n':
		case '\r':
			if (pos < sizeof(line)) {
				line[pos++] = 0;
				execute_line(line);
				pos = 0;
			} else {
				line[sizeof(line) - 1] = 0;
				putstr("Line too long: ");
				puts(line);
			}
			break;
		default:
			if (pos < sizeof(line)) {
				line[pos++] = *p;
			}
			break;
		}
	}
}

static bool wait_for_key(uint32_t us)
{
	start_timer(us);

	while (!timeout())
		if (uart_can_rx())
			return true;

	return false;
}

static void main_loop(void)
{
	char line[128];

	while(1) {
		edit_line(line, sizeof(line));
		execute_line(line);
	}
}

void main(void)
{
	uart_init();

	puts("Press any key to avoid running the default boot script");
	if (!wait_for_key(1000000)) {
		source(_bootscript);
	}

	puts("Welcome to lolmon");
	main_loop();
}

void handle_exception(int number)
{
	static const char *const names[8] = {
		"Reset", "Undefined", "SWI", "Prefetch abort",
		"Data abort", "reserved", "IRQ", "FIQ",
	};

	putchar('\n');
	putstr("Exception ");
	put_hex8(number);
	putstr(", ");
	putstr(names[(number >> 2) & 7]);
	putchar('\n');

	main_loop();
}

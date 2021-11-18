// SPDX-License-Identifier: MIT
// trace.so - an ioctl tracer for iDRAC6's fullfw process
#define _GNU_SOURCE
#include <errno.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <unistd.h>

#define ARRAY_LENGTH(x)	(sizeof(x) / sizeof((x)[0]))

#define IS_MEM_REQ(x)	(((x) & ~0xff) == 0xc004b400)
#define MEM_READ	0xc004b401
#define MEM_WRITE	0xc004b402
#define MEM_REQUEST	0xc004b403
#define MEM_RELEASE	0xc004b404

#define WIDTH_8		0
#define WIDTH_16	1
#define WIDTH_32	2

struct mem_info {
	uint32_t base_addr;
	uint16_t region_size;
	uint16_t offset;
	void *data_ptr;
	uint16_t data_size;
	uint8_t data_width;
	uint8_t id;
};

FILE *log_stream = NULL;

// A new message
void msg(const char *fmt, ...)
{
	va_list ap;
	struct timeval tv;

	if (log_stream) {
		gettimeofday(&tv, NULL);
		fprintf(log_stream, "[%6lu.%03ld] ",
				(unsigned long)tv.tv_sec % 1000000, tv.tv_usec / 1000);

		va_start(ap, fmt);
		vfprintf(log_stream, fmt, ap);
		va_end(ap);
	}
}

// A continuation of a previous message
void cont(const char *fmt, ...)
{
	va_list ap;

	if (log_stream) {
		va_start(ap, fmt);
		vfprintf(log_stream, fmt, ap);
		va_end(ap);
	}
}


static void memdump(struct mem_info *mem)
{
	uint8_t *p8 = mem->data_ptr;
	uint16_t *p16 = mem->data_ptr;
	uint32_t *p32 = mem->data_ptr;
	int i;

	switch (mem->data_width) {
	case WIDTH_8:
		for (i = 0; i < mem->data_size; i++)
			cont(" %02x", p8[i]);
		break;
	case WIDTH_16:
		for (i = 0; i < mem->data_size; i++)
			cont(" %04x", p16[i]);
		break;
	case WIDTH_32:
		for (i = 0; i < mem->data_size; i++)
			cont(" %08x", p32[i]);
		break;
	}
}

static unsigned long bases[32];

static void save_base(const struct mem_info *mem) {
	if (mem->id < ARRAY_LENGTH(bases))
		bases[mem->id] = mem->base_addr;
}

static unsigned long get_address(const struct mem_info *mem) {
	unsigned long base = 0;

	if (mem->id < ARRAY_LENGTH(bases))
		base = bases[mem->id];

	return base + mem->offset;
}

static void trace_mem(int request, struct mem_info *mem)
{
	switch(request) {
	case MEM_REQUEST:
		msg("MEM.REQ%3d %08x:%04x\n", mem->id, mem->base_addr, mem->region_size);
		save_base(mem);
		break;
	case MEM_RELEASE:
		msg("MEM.REL%3d %08x:%04x\n", mem->id, mem->base_addr, mem->region_size);
		break;
	case MEM_READ:
		msg("MEM.RD %3d %08x -> [%2d]", mem->id, get_address(mem), mem->data_size);
		memdump(mem);
		cont("\n");
		break;
	case MEM_WRITE:
		msg("MEM.WR %3d %08x <- [%2d]", mem->id, get_address(mem), mem->data_size);
		memdump(mem);
		cont("\n");
		break;
	}
}

int ioctl(int fd, unsigned long request, ...)
{
	unsigned long arg;
	va_list ap;

	va_start(ap, request);
	arg = va_arg(ap, unsigned long);
	va_end(ap);

	int res = syscall(SYS_ioctl, fd, request, arg);

	if (IS_MEM_REQ(request))
		trace_mem(request, (struct mem_info *)arg);
	else
		msg("UNK.ioctl(%d, %08lx, %08lx)\n", fd, request, arg);

	return res;
}

static void init_trace(void) __attribute__((constructor));
static void init_trace(void)
{
	char filename[100];

	snprintf(filename, sizeof(filename), "/tmp/trace-%d.log", getpid());
	log_stream = fopen(filename, "w");

	msg("Hello from trace.so\n");
}

#define _GNU_SOURCE
#include <stdarg.h>
#include <sys/ioctl.h>
#include <dlfcn.h>
#include <stdio.h>
#include <errno.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <stdint.h>

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
	uint32_t region_size;
	uint16_t offset;
	void *data_ptr;
	uint16_t data_size;
	uint8_t data_width;
	uint8_t id;
};

static void memdump(struct mem_info *mem)
{
	uint8_t *p8 = mem->data_ptr;
	uint16_t *p16 = mem->data_ptr;
	uint32_t *p32 = mem->data_ptr;
	int i;

	switch (mem->data_width) {
	case WIDTH_8:
		for (i = 0; i < mem->data_size; i++)
			printf(" %02x", p8[i]);
		break;
	case WIDTH_16:
		for (i = 0; i < mem->data_size; i++)
			printf(" %04x", p16[i]);
		break;
	case WIDTH_32:
		for (i = 0; i < mem->data_size; i++)
			printf(" %08x", p32[i]);
		break;
	}
}

static void trace_mem(int request, struct mem_info *mem)
{
	switch(request) {
	case MEM_REQUEST:
		printf("REQ%3d %08x:%08x\n", mem->id, mem->base_addr, mem->region_size);
		break;
	case MEM_RELEASE:
		printf("REL%3d %08x:%08x\n", mem->id, mem->base_addr, mem->region_size);
		break;
	case MEM_READ:
		printf("RD %3d %04x ->", mem->id, mem->offset);
		memdump(mem);
		printf("\n");
		break;
	case MEM_WRITE:
		printf("WR %3d %04x <-", mem->id, mem->offset);
		memdump(mem);
		printf("\n");
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
		printf("ioctl(%d, %08lx, %08lx)\n", fd, request, arg);

	return res;
}

static void init_trace(void) __attribute__((constructor));
static void init_trace(void)
{
	// Line buffered mode, so that everything prints out nicely
	setvbuf(stdout, NULL, _IOLBF, 0);

	printf("Hello from trace.so\n");
}

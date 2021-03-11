// SPDX-License-Identifier: MIT
/*
 * Monitor GPIO activity
 */

#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define GPIO	0xb8003000

#define ARRAY_SIZE(x) (sizeof(x) / sizeof(x[0]))

/* Eight ports */
uint32_t regs[8][5] = {
	/*   CFG0       CFG1       CFG2     DATAOUT     DATAIN */
	{ GPIO+0x14, GPIO+0x18,         0, GPIO+0x1c, GPIO+0x20 },
	{ GPIO+0x24, GPIO+0x28, GPIO+0x2c, GPIO+0x34, GPIO+0x38 },
	{ GPIO+0x3c, GPIO+0x40, GPIO+0x44, GPIO+0x48, GPIO+0x4c },
	{ GPIO+0x50, GPIO+0x54, GPIO+0x58, GPIO+0x5c, GPIO+0x60 },
	{ GPIO+0x64, GPIO+0x68, GPIO+0x6c, GPIO+0x70, GPIO+0x74 },
	{ GPIO+0x78, GPIO+0x7c, GPIO+0x80, GPIO+0x84, GPIO+0x88 },
	{         0,         0,         0,         0, GPIO+0x8c },
	{ GPIO+0x90, GPIO+0x94, GPIO+0x98, GPIO+0x9c, GPIO+0xa0 },
};

int main(void) {
	int fd = open("/dev/mem", O_RDONLY);
	if (fd < 0) {
		perror("Failed to open /dev/mem");
		exit(EXIT_FAILURE);
	}

	uint8_t *map = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, GPIO);
	if (map == MAP_FAILED) {
		perror("Failed to map /dev/mem");
		exit(EXIT_FAILURE);
	}
	close(fd);

	printf("        CFG0     CFG1    CFG2    DATAOUT  DATAIN\n");
	for (int port = 0; port < ARRAY_SIZE(regs); port++) {
		printf("[%d] ", port);
		for (int i = 0; i < ARRAY_SIZE(regs[port]); i++) {
			uint32_t addr = regs[port][i];
			if (addr) {
				uint32_t value = *(uint32_t *)(addr - GPIO + map);
				printf(" %08x", value);
			} else {
				printf(" --------");
			}
		}
		printf("\n");
	}

	return 0;
}

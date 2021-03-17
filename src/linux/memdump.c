// SPDX-License-Identifier: MIT
/*
 * memdump - dump a memory range to stdout
 * Usage: memdump START_ADDRESS SIZE
 */

#include <fcntl.h>
#include <unistd.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>

#define PAGE 4096ul /* an assumption that will hopefully not bite me. */
#define PAGE_MASK (PAGE - 1)

int main(int argc, char **argv) {
	if (argc != 3) {
		printf("Usage: memscan START_ADDRESS SIZE\n");
		return EXIT_FAILURE;
	}

	off_t base = strtoul(argv[1], NULL, 0);
	size_t size = strtoul(argv[2], NULL, 0);
	if (size == 0) {
		printf("Size is zero. Exiting.\n");
		exit(EXIT_FAILURE);
	}

	if ((base & PAGE_MASK) || (size & PAGE_MASK)) {
		printf("Base or size not 4k-aligned. Exiting.\n");
		exit(EXIT_FAILURE);
	}

	int fd = open("/dev/mem", O_RDONLY);
	if (fd < 0) {
		perror("Failed to open /dev/mem");
		exit(EXIT_FAILURE);
	}

	void *map = mmap(NULL, size, PROT_READ, MAP_SHARED, fd, base);
	if (map == MAP_FAILED) {
		perror("Failed to map /dev/mem");
		exit(EXIT_FAILURE);
	}

	close(fd);

	fwrite(map, 1, size, stdout);
	fflush(stdout);

	return EXIT_SUCCESS;
}

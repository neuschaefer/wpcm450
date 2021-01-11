// SPDX-License-Identifier: MIT
/*
 * memscan - scan a range in /dev/mem for changes
 * Usage: memscan START_ADDRESS SIZE
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


/* The state of the program */
struct state {
	off_t base;	/* Base address of area to scan */
	size_t size;	/* Size of area to scan */
	uint8_t *copy;	/* Buffer for copy of data */
	uint8_t *map;	/* Mapping */
};

/* Initialize the state */
void init(struct state *state, const char *base, const char *size) {
	state->base = strtoul(base, NULL, 0);
	state->size = strtoul(size, NULL, 0);
	if (size == 0) {
		printf("Size is zero. Exiting.\n");
		exit(EXIT_FAILURE);
	}

	state->copy = malloc(state->size);

	int fd = open("/dev/mem", O_RDONLY);
	if (fd < 0) {
		perror("Failed to open /dev/mem");
		exit(EXIT_FAILURE);
	}

	state->map = mmap(NULL, state->size, PROT_READ, MAP_SHARED, fd, state->base);
	if (state->map == MAP_FAILED) {
		perror("Failed to map /dev/mem");
		exit(EXIT_FAILURE);
	}

	close(fd);

	memcpy(state->copy, state->map, state->size);
}

/* Compare two chunks of memory */
void compare(off_t addr, uint8_t *a, uint8_t *b, size_t size) {
	if (memcmp(a, b, size) == 0) {
		return;
	}

	int linesize = 32; /* bytes per line */
	for (off_t off = 0; off < size; off += linesize) {
		if (memcmp(a + off, b + off, linesize) != 0) {
			printf("%08lx: ", addr + off);
			for (int i = 0; i < linesize; i += 4) {
				printf(" %08x", *(uint32_t *)(b + off + i));
			}
			printf("\n");
		}
	}
}

/* One round of scanning the memory */
void scan(struct state *state) {
	uint8_t buf[4096];

	for (off_t off = 0; off < state->size; off += sizeof(buf)) {
		memcpy(buf, state->map + off, sizeof(buf));
		compare(state->base + off, state->copy + off, buf, sizeof(buf));
		memcpy(state->copy + off, buf, sizeof(buf));
	}
}

/* Main function and busy loop */
int main(int argc, char **argv) {
	if (argc != 3) {
		printf("Usage: memscan START_ADDRESS SIZE\n");
		return EXIT_FAILURE;
	}

	struct state state;
	init(&state, argv[1], argv[2]);

	printf("Scanning at %08lx:%08x\n", state.base, state.size);
	while (true) {
		scan(&state);
	}

	return EXIT_SUCCESS;
}

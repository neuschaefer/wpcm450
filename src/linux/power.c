// SPDX-License-Identifier: MIT
/*
 * A program to manage host power state on Supermicro X9 boards.
 */

#include <fcntl.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <sys/stat.h>
#include <sys/types.h>
#include <sys/ioctl.h>

#include <linux/gpio.h>

#define SHORTPRESS_MS	400
#define LONGPRESS_S	5

#define ARRAY_SIZE(x) (sizeof(x) / sizeof(x[0]))

/* GPIO chip file descriptor */
int fd;

/* individual GPIO line numbers */
int host_powerbtn = -1;
int host_reset = -1;
int host_powersts = -1;

/* GPIOs */
struct gpio {
	const char *name;
	int *line;
};

static struct gpio gpios[] = {
	{ "host_powerbtn", &host_powerbtn },
	{ "host_reset", &host_reset },
	{ "host_powersts", &host_powersts },
};

static void resolve_line_names(void)
{
	struct gpiochip_info chip;
	int res;

	res = ioctl(fd, GPIO_GET_CHIPINFO_IOCTL, &chip);
	if (res < 0) {
		perror("Failed to request GPIO chip information");
		exit(1);
	}

	//printf("Found GPIO chip:\n"
	//       "  %s\n"
	//       "  %s\n"
	//       "  %d lines\n", chip.name, chip.label, chip.lines);

	for (int i = 0; i < chip.lines; i++) {
		struct gpioline_info line;

		line.line_offset = i;
		res = ioctl(fd, GPIO_GET_LINEINFO_IOCTL, &line);
		if (res < 0) {
			perror("Failed to request GPIO line info");
			exit(1);
		}

		if (!line.name[0])
			continue;

		for (int j = 0; j < ARRAY_SIZE(gpios); j++)
			if (strcmp(line.name, gpios[j].name) == 0)
				*gpios[j].line = i;
	}

	bool nope = false;
	for (int j = 0; j < ARRAY_SIZE(gpios); j++) {
		if (*gpios[j].line == -1) {
			printf("Failed to find GPIO line %s\n", gpios[j].name);
			nope = true;
		}
	}
	if (nope)
		exit(1);
}

/* Determine host power status */
bool status(void)
{
	struct gpiohandle_request req;

	req.lineoffsets[0] = host_powersts;
	req.flags = GPIOHANDLE_REQUEST_INPUT;
	strcpy(req.consumer_label, "power status");
	req.lines = 1;

	int res = ioctl(fd, GPIO_GET_LINEHANDLE_IOCTL, &req);
	if (res < 0) {
		perror("Failed to request power status GPIO line");
		exit(1);
	}

	struct gpiohandle_data data;

	res = ioctl(req.fd, GPIOHANDLE_GET_LINE_VALUES_IOCTL, &data);
	if (res < 0) {
		perror("Failed to read host power status");
		exit(1);
	}

	close(req.fd);

	return !!data.values[0];
}

void cmd_status(void)
{
	if (status())
		puts("on");
	else
		puts("off");
}

/* Press the virtual power button for a given number of milliseconds */
void press(int ms)
{
	struct gpiohandle_request req;

	req.lineoffsets[0] = host_powerbtn;
	req.flags = GPIOHANDLE_REQUEST_OUTPUT | GPIOHANDLE_REQUEST_ACTIVE_LOW;
	req.default_values[0] = 0;
	strcpy(req.consumer_label, "power button");
	req.lines = 1;

	int res = ioctl(fd, GPIO_GET_LINEHANDLE_IOCTL, &req);
	if (res < 0) {
		perror("Failed to request power button GPIO line");
		exit(1);
	}

	struct gpiohandle_data data;

	data.values[0] = 1;
	res = ioctl(req.fd, GPIOHANDLE_SET_LINE_VALUES_IOCTL, &data);
	if (res < 0) {
		perror("Failed to press power button");
		exit(1);
	}

	usleep(1000 * ms);

	data.values[0] = 0;
	res = ioctl(req.fd, GPIOHANDLE_SET_LINE_VALUES_IOCTL, &data);
	if (res < 0) {
		perror("Failed to release power button");
		exit(1);
	}

	close(req.fd);
}

static void cmd_longpress(void)
{
	press(LONGPRESS_S * 1000);
}

static void cmd_shortpress(void)
{
	press(SHORTPRESS_MS);
}

void cmd_on(void)
{
	if (!status())
		cmd_shortpress();
}

void cmd_off(void)
{
	if (status())
		cmd_longpress();
}

static void wait(bool target)
{
	while (status() != target) {
		usleep(50 * 1000);
	}
}

static void cmd_shutdown()
{
	cmd_shortpress();
	wait(false);
}

int main(int argc, char **argv)
{
	if (argc != 2) {
		printf("Usage: %s [ACTION]\n\n", argv[0]);

		printf("Actions:\n");
		printf("  - status      query the current status (default)\n");
		printf("  - on          turn the power on\n");
		printf("  - off         turn the power off\n");
		printf("  - shutdown    kindly ask the OS to shut down\n");
		printf("  - shortpress  press the power button for a short time (%dms)\n", SHORTPRESS_MS);
		printf("  - longpress   press the power button for a long time (%ds)\n", LONGPRESS_S);
		exit(0);
	};

	fd = open("/dev/gpiochip0", O_RDWR);
	if (fd < 0) {
		perror("Failed to open /dev/gpiochip0");
		exit(1);
	}

	resolve_line_names();

	const char *action = argv[1];

	if (!strcmp(action, "status"))
		cmd_status();
	else if (!strcmp(action, "on"))
		cmd_on();
	else if (!strcmp(action, "off"))
		cmd_off();
	else if (!strcmp(action, "shutdown"))
		cmd_shutdown();
	else if (!strcmp(action, "shortpress") || !strcmp(action, "boop"))
		cmd_shortpress();
	else if (!strcmp(action, "longpress"))
		cmd_longpress();
	else
		printf("Unknown action %s\n", action);

	return 0;
}

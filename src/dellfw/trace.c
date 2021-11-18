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

#define IS_MEM(x)	(((x) & ~0xff) == 0xc004b400)
#define MEM_READ	0xc004b401
#define MEM_WRITE	0xc004b402
#define MEM_REQUEST	0xc004b403
#define MEM_RELEASE	0xc004b404

#define IS_IRQ(x)	(((x) & ~0xff) == 0xc004b900)
#define IRQ_DRV_INIT	0xc004b900
#define IRQ_DYN_INIT	0xc004b901
#define IRQ_DYN_CONFIG	0xc004b902
#define IRQ_DYN_CLEAR	0xc004b903
#define IRQ_GEN_INIT	0xc004b904
#define IRQ_UM_ISRID	0xc004b905

#define IS_GPIO(x)	(((x) & ~0xff) == 0xc004b500)
#define GPIO_READ	0xc004b500
#define GPIO_WRITE	0xc004b501
#define GPIO_CONFIG	0xc004b502

#define IS_I2C(x)	(((x) & ~0xff) == 0xc014b700)
#define I2C_INIT	0xc014b700
#define I2C_CONFIG	0xc014b701
#define I2C_WRITE	0xc014b702
#define I2C_GET_MSG	0xc014b703
#define I2C_RESET	0xc014b704
#define I2C_GET_STAT	0xc014b705
#define I2C_GET_HWSTAT	0xc014b706
#define I2C_CTRL_HW	0xc014b707

#define IS_PWM(x)	(((x) & ~0xff) == 0xc004be00)
#define PWM_INIT	0xc004be00
#define PWM_SET		0xc004be01
#define PWM_INFO	0xc004be02
#define PWM_DEBUG	0xc004be03

#define IS_POST(x)	(((x) & ~0xff) == 0xc004cf00)
#define POST_INIT	0xc004cf00
#define POST_READ	0xc004cf01
#define POST_RESET	0xc004cf02

#define IS_KCS(x)	(((x) & ~0xff) == 0xc004ba00)
#define KCS_INIT	0xc004ba00
#define KCS_READ	0xc004ba01
#define KCS_WRITE	0xc004ba02
#define KCS_SWSMI	0xc004ba03
#define KCS_SETCBID	0xc004ba04

#define IS_SSPI(x)	(((x) & ~0xff) == 0xc014c500)
#define SSPI_WRITE	0xc014c501


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


#define MEM_WIDTH_8	0
#define MEM_WIDTH_16	1
#define MEM_WIDTH_32	2

struct mem_info {
	uint32_t base_addr;
	uint16_t region_size;
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
	case MEM_WIDTH_8:
		for (i = 0; i < mem->data_size; i++)
			cont(" %02x", p8[i]);
		break;
	case MEM_WIDTH_16:
		for (i = 0; i < mem->data_size; i++)
			cont(" %04x", p16[i]);
		break;
	case MEM_WIDTH_32:
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
		msg(" MEM.REQ%3d %08x:%04x\n", mem->id, mem->base_addr, mem->region_size);
		save_base(mem);
		break;
	case MEM_RELEASE:
		msg(" MEM.REL%3d %08x:%04x\n", mem->id, mem->base_addr, mem->region_size);
		break;
	case MEM_READ:
		msg(" MEM.RD %3d %08x -> [%2d]", mem->id, get_address(mem), mem->data_size);
		memdump(mem);
		cont("\n");
		break;
	case MEM_WRITE:
		msg(" MEM.WR %3d %08x <- [%2d]", mem->id, get_address(mem), mem->data_size);
		memdump(mem);
		cont("\n");
		break;
	default:
		msg(" MEM.UNK %d\n", request & 0xff);
		break;
	}
}


struct irq_info {
	uint16_t param1; /* IRQ number */
	uint16_t param2;
	uint32_t param3;
	const char *isr_name;
};

static void trace_irq(unsigned long request, void *arg)
{
	struct irq_info *irq = arg;

	switch (request) {
	case IRQ_DRV_INIT:
		msg(" IRQ.INIT driver\n");
		break;
	case IRQ_DYN_INIT:
		msg(" IRQ.INIT dynairq %3d %04x %08x %p\n",
				irq->param1, irq->param2, irq->param3, irq->isr_name);
		break;
	default:
		msg(" IRQ.UNK %d\n", request & 0xff);
		break;
	}
}


struct gpio_data {
	uint8_t command_type;
	uint8_t command_num;
	uint8_t port_num;
	uint8_t pin_num;
	void *buf;
};

static void trace_gpio(unsigned long request, struct gpio_data *gpio)
{
	uint8_t *p8 = gpio->buf;

	switch (request) {
	case GPIO_READ:
		msg("GPIO.RD %d %2d -> %d\n", gpio->port_num, gpio->pin_num, *p8);
		break;
	case GPIO_WRITE:
		msg("GPIO.WR %d %2d <- %d\n", gpio->port_num, gpio->pin_num, *p8);
		break;
	case GPIO_CONFIG:
		msg("GPIO.CFG\n");
		break;
	default:
		msg("GPIO.UNK %d\n", request & 0xff);
		break;
	}
}


struct i2c_bus_info {
	uint32_t rec_flag;
	uint16_t driver_id;
	uint16_t start_count;
	uint16_t stop_count;
	uint8_t channel;
	uint8_t init_mode;
	uint8_t mode;
	uint8_t dev_addr;
	uint8_t freq;
	uint8_t error_status;
	uint8_t bus_status;
	uint8_t hw_ctrl;
	uint8_t trans_type;
	uint8_t reserved;
};

struct i2c_buf_info {
	uint8_t *send_buf;
	uint8_t *recv_buf;
	uint16_t reserved;
	uint8_t channel;
	uint8_t dev_addr;
	uint8_t error_status;
	uint8_t send_size;
	uint8_t recv_size;
	uint8_t trans_type;
};

static void trace_i2c(unsigned long request, void *arg)
{
	struct i2c_bus_info *bus = arg;
	struct i2c_buf_info *buf = arg;

	switch (request) {
	default:
		msg(" I2C.UNK %d\n", request & 0xff);
		break;
	}
}


struct pwm_dev_config {
	uint8_t channel;
	uint8_t base_freq;
	uint8_t freq_div;
	uint8_t duty_cycle;
};

static void trace_pwm(unsigned long request, struct pwm_dev_config *pwm)
{
	switch (request) {
	default:
		msg(" PWM.UNK %d\n", request & 0xff);
		break;
	}
}


struct bios_post_info {
	uint16_t max_read_len;
	uint16_t copy_len;
	uint8_t addr_lsb;
	uint8_t addr_msb;
	uint8_t addr_enable;
	uint8_t reserved;
	uint8_t *buf;
};

static void trace_post(unsigned long request, struct bios_post_info *post)
{
	switch (request) {
	default:
		msg("POST.UNK %d\n", request & 0xff);
		break;
	}
}


struct kcs_info {
	uint8_t channel;
	uint8_t control;
	uint16_t base_addr;
	uint8_t write_len;
	/* [three bytes of padding] */
	uint8_t *read_len;
	uint8_t *data;
	uint32_t rx_ok_event;
	uint32_t tx_ok_event;
	uint32_t tx_fail_event;
	uint16_t driver_id;
	uint16_t callback_driver_id;
	uint32_t callback_event_id;
};

static void trace_kcs(unsigned long request, struct kcs_info *kcs)
{
	switch (request) {
	default:
		msg(" KCS.UNK %d\n", request & 0xff);
		break;
	}
}


struct sspi_info {
	uint8_t proc_time;
	uint8_t mode;
	uint8_t chip_select;
	uint8_t speed;
	uint8_t *send_buf;
	uint32_t send_size;
	uint8_t *recv_buf;
	uint32_t recv_size;
};

static void trace_sspi(unsigned long request, struct sspi_info *sspi)
{
	switch (request) {
	default:
		msg("SSPI.UNK %d\n", request & 0xff);
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

	if (IS_MEM(request))
		trace_mem(request, (struct mem_info *)arg);
	else if (IS_IRQ(request))
		trace_irq(request, (void *)arg);
	else if (IS_GPIO(request))
		trace_gpio(request, (struct gpio_data *)arg);
	else if (IS_I2C(request))
		trace_i2c(request, (void *)arg);
	else if (IS_PWM(request))
		trace_pwm(request, (struct pwm_dev_config *)arg);
	else if (IS_POST(request))
		trace_post(request, (struct bios_post_info *)arg);
	else if (IS_KCS(request))
		trace_kcs(request, (struct kcs_info *)arg);
	else if (IS_SSPI(request))
		trace_sspi(request, (struct sspi_info *)arg);
	else
		msg(" UNK.ioctl(%d, %08lx, %08lx)\n", fd, request, arg);

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

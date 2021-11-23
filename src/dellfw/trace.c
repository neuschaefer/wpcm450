// SPDX-License-Identifier: MIT
// trace.so - an ioctl tracer for iDRAC6's fullfw process
#define _GNU_SOURCE
#include <errno.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>

#define ARRAY_LENGTH(x)	(sizeof(x) / sizeof((x)[0]))

#define IOCTL_TYPE(x)	(((x) & 0xff00) >> 8)
#define IOCTL_TYPENR(x)	((x) & 0xffff)

#define TYPE_MEM	0xb4
#define MEM_READ	0xb401
#define MEM_WRITE	0xb402
#define MEM_REQUEST	0xb403
#define MEM_RELEASE	0xb404

#define TYPE_IRQ	0xb9
#define IRQ_DRV_INIT	0xb900
#define IRQ_DYN_INIT	0xb901
#define IRQ_DYN_CONFIG	0xb902
#define IRQ_DYN_CLEAR	0xb903
#define IRQ_GEN_INIT	0xb904
#define IRQ_UM_ISRID	0xb905

#define TYPE_GPIO	0xb5
#define GPIO_READ	0xb500
#define GPIO_WRITE	0xb501
#define GPIO_CONFIG	0xb502

#define TYPE_I2C	0xb7
#define I2C_INIT	0xb700
#define I2C_CONFIG	0xb701
#define I2C_WRITE	0xb702
#define I2C_GET_MSG	0xb703
#define I2C_RESET	0xb704
#define I2C_GET_STAT	0xb705
#define I2C_GET_HWSTAT	0xb706
#define I2C_CTRL_HW	0xb707

#define TYPE_PWM	0xbe
#define PWM_INIT	0xbe00
#define PWM_SET		0xbe01
#define PWM_INFO	0xbe02
#define PWM_DEBUG	0xbe03

#define TYPE_POST	0xcf
#define POST_INIT	0xcf00
#define POST_READ	0xcf01
#define POST_RESET	0xcf02

#define TYPE_KCS	0xba
#define KCS_INIT	0xba00
#define KCS_READ	0xba01
#define KCS_WRITE	0xba02
#define KCS_SWSMI	0xba03
#define KCS_SETCBID	0xba04

#define TYPE_SSPI	0xc5
#define SSPI_WRITE	0xc501


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
	switch (IOCTL_TYPENR(request)) {
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

struct irq_usermode_record {
	uint16_t num_irq;
	uint32_t event_id;
};

static void trace_irq(unsigned long request, void *arg)
{
	struct irq_info *irq = arg;
	struct irq_usermode_record *um = arg;
	uint16_t *driver_id = arg;

	switch (IOCTL_TYPENR(request)) {
	case IRQ_DRV_INIT:
		msg(" IRQ.INIT driver\n");
		break;
	case IRQ_DYN_INIT:
		msg(" IRQ.INIT dynairq %3d %04x %08x %p\n",
				irq->param1, irq->param2, irq->param3, irq->isr_name);
		break;
	case IRQ_DYN_CONFIG:
		msg(" IRQ.CFG  dynairq %3d %04x %08x %p\n",
				irq->param1, irq->param2, irq->param3, irq->isr_name);
		break;
	case IRQ_DYN_CLEAR:
		msg(" IRQ.CLR  dynairq %3d\n", irq->param1);
		break;
	case IRQ_GEN_INIT:
		msg(" IRQ.INIT geneisr driver %d\n", *driver_id);
		break;
	case IRQ_UM_ISRID:
		msg(" IRQ.UM   irq %d %d\n", um->num_irq, um->event_id);
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

	switch (IOCTL_TYPENR(request)) {
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

	switch (IOCTL_TYPENR(request)) {
	case I2C_INIT:
		msg(" I2C.INIT %d ...\n",
				bus->channel);
		break;
	case I2C_WRITE:
		msg(" I2C.WR   %d ...\n",
				buf->channel);
		break;
	case I2C_GET_HWSTAT:
		msg(" I2C.HW   %d ...\n",
				bus->channel);
		break;
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
	switch (IOCTL_TYPENR(request)) {
	case PWM_INIT:
		msg(" PWM.INIT %d <- duty %d, freq %d, div %d\n",
				pwm->channel, pwm->duty_cycle, pwm->base_freq, pwm->freq_div);
		break;
	case PWM_SET:
		msg(" PWM.SET  %d <- duty %d, freq %d, div %d\n",
				pwm->channel, pwm->duty_cycle, pwm->base_freq, pwm->freq_div);
		break;
	case PWM_INFO:
		msg(" PWM.INFO %d -> duty %d, freq %d, div %d\n",
				pwm->channel, pwm->duty_cycle, pwm->base_freq, pwm->freq_div);
		break;
	case PWM_DEBUG:
		msg(" PWM.DBG  %d <- duty %d, freq %d, div %d\n",
				pwm->channel, pwm->duty_cycle, pwm->base_freq, pwm->freq_div);
		break;
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

static void dump_u8_buf(const uint8_t *buf, size_t size)
{
	int i;

	for (i = 0; i < size; i++)
		cont(" %02x", buf[i]);
}

static void trace_post(unsigned long request, struct bios_post_info *post)
{
	switch (IOCTL_TYPENR(request)) {
	case POST_INIT:
		msg("POST.INIT %d %02x%02x\n", post->addr_enable, post->addr_msb, post->addr_lsb);
		break;
	case POST_READ:
		msg("POST.RD   [%d]\n", post->copy_len);
		dump_u8_buf(post->buf, post->copy_len);
		cont("\n");
		break;
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
	switch (IOCTL_TYPENR(request)) {
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
	switch (IOCTL_TYPENR(request)) {
	case SSPI_WRITE:
		msg("SSPI.WRITE %d, time %3d, mode %02x, speed %3d, [%d,%d] ",
				sspi->chip_select, sspi->proc_time, sspi->mode, sspi->speed,
				sspi->send_size, sspi->recv_size);
		dump_u8_buf(sspi->send_buf, sspi->send_size);
		cont(" -> ");
		dump_u8_buf(sspi->recv_buf, sspi->recv_size);
		cont("\n");
		break;
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

	switch (IOCTL_TYPE(request)) {
	case TYPE_MEM:
		trace_mem(request, (struct mem_info *)arg);
		break;
	case TYPE_IRQ:
		trace_irq(request, (void *)arg);
		break;
	case TYPE_GPIO:
		trace_gpio(request, (struct gpio_data *)arg);
		break;
	case TYPE_I2C:
		trace_i2c(request, (void *)arg);
		break;
	case TYPE_PWM:
		trace_pwm(request, (struct pwm_dev_config *)arg);
		break;
	case TYPE_POST:
		trace_post(request, (struct bios_post_info *)arg);
		break;
	case TYPE_KCS:
		trace_kcs(request, (struct kcs_info *)arg);
		break;
	case TYPE_SSPI:
		trace_sspi(request, (struct sspi_info *)arg);
		break;
	default:
		msg(" UNK.ioctl(%d, %08lx, %08lx)\n", fd, request, arg);
	}

	return res;
}


struct event_data {
	uint16_t driver_id;
	// uint16_t padding;
	uint32_t event_id;
};

static void trace_event(struct event_data *event, size_t count, ssize_t res)
{
	// aess_eventhandler_read returns zero on success, contrary to how read(2) should work.
	if (count != 8 || res != 0) {
		msg("  EV.GET: Unusual read from eventhandler FD: %zu %zd\n", count, res);
		return;
	}

	msg("  EV.GET driver %u, event %u\n", event->driver_id, event->event_id);
}


static int eventhandler_fd = -1;

int open(const char *pathname, int flags, mode_t mode)
{
	int res = syscall(SYS_open, pathname, flags, mode);

	if (strcmp(pathname, "/dev/aess_eventhandlerdrv") == 0)
		eventhandler_fd = res;

	return res;
}

ssize_t read(int fd, void *buf, size_t count)
{
	ssize_t res = syscall(SYS_read, fd, buf, count);

	if (eventhandler_fd >= 0 && fd == eventhandler_fd)
		trace_event(buf, count, res);

	return res;
}

static void init_trace(void) __attribute__((constructor));
static void init_trace(void)
{
	char filename[100];

	snprintf(filename, sizeof(filename), "/tmp/trace-%d.log", getpid());
	log_stream = fopen(filename, "w");
	if (log_stream) {
		setlinebuf(log_stream);
		msg("Hello from trace.so\n");
	}
}

	# SPDX-License-Identifier: MIT
	# Retrieve the baud rate divisor of UART0 and UART1
	# Assumes UART0 @ 0xb8000000, UART1 @ 0xb8000100
	# Stores the divisors at 0x0 (UART0), 0x4 (UART1)
.global	_start
_start:
	mov	r1, #0
	mov	r2, #0xb8000000
	mov	r7, lr

	bl	getdiv
	str	r0, [r1]

	add	r0, #0x100
	bl	getdiv
	str	r0, [r1, #4]

	bx	r7


	# getdiv - Retrieve the divisor for the UART @ r2, return value in r0.
getdiv:
	# Set Line Control Register / Data Latch Access Bit
	ldr	r3, [r2, #0xc]
	orr	r3, #0x80
	str	r3, [r2, #0xc]

	# Read Divisor Latch
	ldrb	r0, [r2, #0]
	ldrb	r3, [r2, #4]
	lsl	r3, #8
	orr	r0, r3

	# Clear Line Control Register / Data Latch Access Bit
	ldr	r3, [r2, #0xc]
	bic	r3, #0x80
	str	r3, [r2, #0xc]

	bx	lr

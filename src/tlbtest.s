	# SPDX-License-Identifier: MIT
	# TLB flush operation test program
	# to see if anything hangs the system
.global	_start
_start:
	mov	r0, #0
	mov	r1, #0xb8000000

	mov     r2, #'A' // checkpoint A
	str	r2, [r1]

	mcr	p15, 0, r0, c8, c7, 0  // Invalidate TLB

	mov     r2, #'B'
	str	r2, [r1]

	mcr	p15, 0, r0, c8, c6, 0  // Invalidate data TLB

	mov     r2, #'C'
	str	r2, [r1]

	mcr	p15, 0, r0, c8, c5, 0  // Invalidate instruction TLB

	mov     r2, #'D'
	str	r2, [r1]

	# return
	bx	lr

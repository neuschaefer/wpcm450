# SPDX-License-Identifier: MIT

.global _start
_start:
	# Lets mostly follow https://www.kernel.org/doc/Documentation/arm/Booting
	# to make sure that Linux boots
	# - CPU mode
	#   All forms of interrupts must be disabled (IRQs and FIQs)
	#
	# - Caches, MMUs
	#   The MMU must be off.
	#   Instruction cache may be on or off.
	#   Data cache must be off.

	# Leave IRQ and FIQ unchanged. They can be useful, but only if the
	# previous-stage bootloader didn't expect interrupts.
	#mrs	r0, cpsr
	#bic	r0, #0xc0
	#msr	cpsr, r0

	bl	main
loop:	b	loop


.global instruction_memory_barrier
instruction_memory_barrier:
	# See ARM926EJ-S Technical Reference Manual, 9.2 IMB operation

	# 9.2.1 Clean the DCache
dcache_loop:
	push	{r0, lr}

	mrc	p15, 0, r15, c7, c10, 3
	bne	dcache_loop

	# 9.2.2 Drain write buffer
	mcr	p15, 0, r0, c7, c10, 4

	# 9.2.3 Synchronize data and instruction streams in level two AHB subsystems
	# no idea really, but let's read from uncached memory
	mov	r0, #0x40000000
	ldr	r0, [r0]

	# 9.2.4 Invalidate the ICache
	mcr	p15, 0, r0, c7, c5, 0

	# 9.2.5 Flush the prefetch buffer
	b	new_world
new_world:

	pop	{r0, pc}


.global do_call
do_call:
	# in: r0: function address
	#     r1-r3: arguments

	push	{r0-r4, lr}

	mov	r4, r0
	mov	r0, r1
	mov	r1, r2
	mov	r2, r3

	blx	r4

	pop	{r0-r4, pc}

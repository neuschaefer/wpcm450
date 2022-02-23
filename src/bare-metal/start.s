# SPDX-License-Identifier: MIT

.global _start
_start:
	# Exception vector:
	b	reset		@ 0x0000: Reset
	bl	exception	@ 0x0004: Undefined
	bl	exception	@ 0x0008: SWI
	bl	exception	@ 0x000c: Prefetch abort
	bl	exception	@ 0x0010: Data abort
	bl	exception	@ 0x0014: reserved
	bl	exception	@ 0x0018: IRQ
	bl	exception	@ 0x001c: FIQ
exception:
	mov	r0, lr		@ save exception vector offset
	sub	r0, #4

	mrs	r1, cpsr	@ switch to supervisor mode
	bic	r1, #0x1f
	orr	r1, #0x13
	msr	cpsr, r1

	mov	sp, #0x2000
	bl	handle_exception
	b	loop

reset:
	# Lets mostly follow https://www.kernel.org/doc/Documentation/arm/Booting
	# to make sure that Linux boots
	# - CPU mode
	#   All forms of interrupts must be disabled (IRQs and FIQs)
	#
	# - Caches, MMUs
	#   The MMU must be off.
	#   Instruction cache may be on or off.
	#   Data cache must be off.

	# Disable IRQ and FIQ.
	mrs	r0, cpsr
	bic	r0, #0xc0
	msr	cpsr, r0

	# Disable data cache and MMU, use low vector base
	mrc	p15, 0, r0, c1, c0, 0
	#bic	r0, #4      @ DCache
	bic	r0, #1      @ MMU
	bic	r0, #0x2000 @ low vectors (@0x00000000)
	mcr	p15, 0, r0, c1, c0, 0

	# Set the stack pointer to the end of internal RAM @ 0x0
	mov	sp, #0x2000

	# Copy lolmon to internal RAM @ 0x0
	adr	r0, _start
	mov	r1, #0
	mov	r2, #0x2000
copy:
	ldr	r3, [r0], #4
	ldr	r4, [r0], #4
	ldr	r5, [r0], #4
	ldr	r6, [r0], #4
	str	r3, [r1], #4
	str	r4, [r1], #4
	str	r5, [r1], #4
	str	r6, [r1], #4
	subs	r2, #16
	bne	copy

	# Switch to internal RAM, in order to be independent from DRAM
	bl	instruction_memory_barrier
	ldr	r0, =welcome_to_iram
	bx	r0
welcome_to_iram:

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
	# no idea really, but let's read from uncached memory (TODO)
	mov	r0, #0x00000000  // not sure if uncached
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

        # scream on the debug uart.
.global _start
_start:
        mov     r0, #0xb8000000
        mov     r1, #'A'
a:      strb    r1, [r0,#0x00]
        b       a

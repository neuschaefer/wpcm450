/* SPDX-License-Identifier: MIT */

SECTIONS {
	. = 0x00008000;

	.text : {
		*(.text*);
	}

	.rodata : {
		*(.rodata*);
		*(.data.rel.ro*);
	}

	. = 0x0000c000;
	.bootscript : {
                _bootscript = .;
		*(.bootscript);
	}
}

/* SPDX-License-Identifier: MIT */

SECTIONS {
	. = 0x0000;

	.text : {
		*(.text*);
	}

	.rodata : {
		*(.rodata*);
		*(.data.rel.ro*);
	}

	. = 0x1800;
	.bootscript : {
                _bootscript = .;
		*(.bootscript);
	}
}

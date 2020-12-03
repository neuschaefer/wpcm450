/* SPDX-License-Identifier: MIT */

SECTIONS {
	. = 0x06400000;

	.text : {
		*(.text*);
	}

	.rodata : {
		*(.rodata*);
		*(.data.rel.ro*);
	}

	. = 0x06404000;
	.bootscript : {
                _bootscript = .;
		*(.bootscript);
	}
}

<!-- SPDX-License-Identifier: MIT -->
<!-- Copyright (C) J. Neuschäfer -->

# Dell iDRAC6 firmware tools

The main thing here is `trace.so`, which can be `LD_PRELOAD`-ed into the
`fullfw` process running on Dell boards, to trace interesting ioctls.


## Build instructions

Building with a toolchain that uses a recent glibc will not work, because
`trace.so` will contain references to symbol version not present in Dell
firmware (e.g. `printf@GLIBC_2.4` on my system).

Building with a musl-based toolchain will work fairly well, but you may have to
fix the binary with `patchelf --replace-needed libc.so libc.so.6 trace.so`.

`make CC=/path/to/arm-linux-gcc`


## Usage

- `/tmp/DellFS` is a good place to put trace.so. You can upload it with
  `make uuencode` and `uudecode && gunzip trace.so.gz`.
- `killall fullfw && LD_PRELOAD=/path/to/trace.so fullfw`
- TODO: appease the `AppMonitor`
- read traces from `/tmp/trace*.log`


## References

- [Kernel module source code for iDRAC6 1.70](https://github.com/neuschaefer/linux/tree/vendor/dell-idrac6-1.70/drivers/dell)

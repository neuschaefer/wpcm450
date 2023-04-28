# LOLBMC - Minimal firmware for BMCs

To build:

- Download [Buildroot](https://buildroot.org/)
- Copy or symlink your buildroot source directory to ./buildroot
- run `./make.sh lolbmc_defconfig`
- run `./make.sh -j5` and sit back
- Enjoy the files in `out/images/`

#!/bin/sh

if [ ! -e buildroot ]; then
	echo "Buildroot symlink is missing. Please run \"ln -s ~/path/to/buildroot buildroot\"."
	return 1
fi

make -C buildroot BR2_EXTERNAL="$PWD" O="$PWD/out" "$@"

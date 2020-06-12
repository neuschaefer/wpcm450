#!/bin/sh
# SPDX-License-Identifier: MIT
# Apply the patches from an AMI GPL source package to a git repo
set -e

if [ $# != 1 ]; then
	echo "usage: $0 path/to/winbond/patches/linux"
	exit 1
fi
PATCHDIR="$1"


(
	cd "$PATCHDIR"
	find . -type f
) | cut -d/ -f2- | sort | while read filename; do
	echo "Applying $filename"
	patch -p1 < "$PATCHDIR/$filename"
	git add .
	git commit -m "Apply $filename"
	sleep 1
done

#!/bin/sh
set -e

# Version information:

BUILDROOT_VERSION="$(cd "$SRCDIR" && git describe --always)"
LOLBMC_VERSION="$(cd "$BR2_EXTERNAL_LOLBMC_PATH" && git describe --always)"
pwd
ls -l "$1"

sed -i \
	-e 's/<!-- INSERT_LOLBMC_GIT_VERSION: -->.*$/'"$LOLBMC_VERSION"/ \
	-e 's/<!-- INSERT_BUILDROOT_GIT_VERSION: -->.*$/'"$BUILDROOT_VERSION"/ \
	"$1/var/www/index.html"


# SSH Stuff:
#
# 1. /etc/dropbox is created as a symlink, and later (at runtime) recreated as
#    a real directory. This causes some issues with persistence, so let's not
#    be clever.
# 2. When ssh-copy-id detects dropbear, it places the key for root in
#    /etc/dropbear, which isn't really where dropbear expects it.

rm -rf "$1/etc/dropbear" "$1/root/.ssh"
mkdir "$1/etc/dropbear" "$1/root/.ssh"
ln -s /etc/dropbear/authorized_keys "$1/root/.ssh/authorized_keys"

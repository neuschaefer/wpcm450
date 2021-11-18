#!/bin/sh
# SPDX-License-Identifier: MIT
#
# run-fullfw.sh - Script that runs fullfw with tracing, and makes sure
# AppMonitor doesn't get upset.

HERE="$(dirname "$(realpath "$0")")"

killall fullfw
cd /flash/data0/BMC_Data
LD_PRELOAD="$HERE/trace.so" exec /etc/sysapps_script/S_3150_fullfw_app.sh restart

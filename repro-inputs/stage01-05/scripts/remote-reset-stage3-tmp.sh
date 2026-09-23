#!/bin/bash
set -e

base=/home/openeuler/build/tl3572-2oo3
bad_tmp=${base}/build/build-tl3572/tmp-mixed-hosttools-20260916
current_tmp=${base}/build/build-tl3572/tmp

if [ -d ${current_tmp} ]; then
    if [ -e ${bad_tmp} ]; then
        echo "Refusing to overwrite preserved diagnostic directory: ${bad_tmp}" >&2
        exit 1
    fi
    mv ${current_tmp} ${bad_tmp}
fi

mkdir -p ${base}/sstate-stage3
echo PRESERVED_TMP=${bad_tmp}
echo CLEAN_TMP=${current_tmp}
echo STAGE3_SSTATE=${base}/sstate-stage3


#!/bin/sh
set -eu
mkdir -p /config/custom_components
if [ ! -e /config/custom_components/leelen3 ] && [ ! -L /config/custom_components/leelen3 ]; then
    ln -s /opt/custom_components/leelen3 /config/custom_components/leelen3
fi
exec /init "$@"

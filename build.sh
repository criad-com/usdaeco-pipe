#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
TOOLCHAIN_DIR="${TOOLCHAIN_DIR:-$HERE/../usdaeco-toolchain}"
CORE_DIR="${AECO_CORE_ROOT:-${CORE_DIR:-$HERE/../usdaeco-core}}"
bash "$TOOLCHAIN_DIR/build.sh" usdAecoPipe "$HERE" \
    --dep "${CORE_PLUGIN_DIR:-$CORE_DIR/out/plugins/usdAeco/resources}" \
    --dep "${AXIS_PLUGIN_DIR:-$HERE/../usdaeco-axis/out/plugins/usdAecoAxis/resources}" "$@"
while (( $# )); do
    if [[ "$1" == "--install-root" ]]; then
        mkdir -p "$2/python"
        cp -RL "$HERE/tools/usdaeco_pipe" "$2/python/"
        break
    fi
    shift
done

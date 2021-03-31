#!/usr/bin/env bash

_term() { 
  echo "Caught SIGINT signal!" 
  kill -INT "$child"
}

trap _term SIGINT

set -Euxo pipefail

export LD_LIBRARY_PATH=/home/eval/lib/

afl-clang-lto++ /home/eval/lib/libdynamiclibrary.so $1 $2

[[ -d output ]] && rm -rf output
mkdir output

shift
shift

SEEDS="$1"

shift

export TRIGGERED_OUTPUT="$@"
export TRIGGERED_FILE="$(pwd)/covered"
export AFL_NO_AFFINITY=1
exec afl-fuzz -d -i $SEEDS -o output -- ./a.out $@ &

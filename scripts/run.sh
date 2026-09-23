#!/bin/bash
# Docker entry point: `ibmq` runs the QAOA experiments, `bash` opens a shell.

if [ $# -eq 0 ]; then
	echo "Usage: ./scripts/run.sh [ibmq|bash]"
	exit 1
fi

cd /home/repro/sigmod-repro/

if [ "$1" = "ibmq" ]; then
	./scripts/run_ibmq.sh
elif [ "$1" != "bash" ]; then
	echo "Usage: ./scripts/run.sh [ibmq|bash]"
fi

/bin/bash

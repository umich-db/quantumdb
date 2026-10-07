#!/bin/bash
# Waits for the Week93-95 diverse multi-start pipelines in the sigmod-repro container
# to finish, then copies every output (energy logs, readouts, SPIQ files, logs) to this repo.
REPO=/Users/divyashekar/Documents/Sem3/QuantumDB/sigmod23-reproduction
C=sigmod-repro; CROOT=/home/repro/sigmod-repro
echo "watcher start $(date)"
sleep 60
while true; do
  n=$(docker exec $C pgrep -fc diverse_run.sh 2>/dev/null)
  if [ -z "$n" ]; then echo "$(date) docker not reachable, retrying"; sleep 120; continue; fi
  [ "$n" -eq 0 ] && break
  sleep 300
done
echo "pipelines finished $(date)"
for pair in "0 Week93" "1 Week94" "2 Week95"; do
  set -- $pair; IDX=$1; W=$2
  docker exec $C test -d $CROOT/base/$W && docker cp $C:$CROOT/base/$W $REPO/base/ && echo "copied base/$W"
  docker exec $C test -d $CROOT/$W && docker cp $C:$CROOT/$W $REPO/ && echo "copied $W"
  mkdir -p $REPO/spiq_init_outputs
  docker exec $C test -d $CROOT/spiq_init_outputs/diverse_$W && docker cp $C:$CROOT/spiq_init_outputs/diverse_$W $REPO/spiq_init_outputs/ && echo "copied spiq_init_outputs/diverse_$W"
  docker cp $C:$CROOT/diverse_${W}_input${IDX}.log $REPO/logs/ && echo "copied logs/diverse_${W}_input${IDX}.log"
  grep -q "=== all done" $REPO/logs/diverse_${W}_input${IDX}.log && echo "$W: COMPLETE" || echo "$W: INCOMPLETE - check logs/diverse_${W}_input${IDX}.log"
done
echo "watcher done $(date)"

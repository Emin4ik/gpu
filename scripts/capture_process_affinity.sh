#!/bin/sh
set -eu

if [ "$#" -lt 3 ]; then
  echo "usage: $0 <rank> <pid> <role> [node]" >&2
  exit 2
fi

rank=$1
pid=$2
role=$3
node=${4:-$(hostname)}
status_file="/proc/$pid/status"

if [ ! -r "$status_file" ]; then
  echo "cannot read $status_file" >&2
  exit 1
fi

cpus=$(awk '/^Cpus_allowed_list:/ { print $2; exit }' "$status_file")
printf 'rank,pid,role,cpu_list,node\n'
printf '%s,%s,%s,"%s",%s\n' "$rank" "$pid" "$role" "$cpus" "$node"

#!/usr/bin/env bash
set -euo pipefail

# Run once per rank under srun/torchrun and aggregate stdout into rank-map.csv.
# Example header:
# rank,node,local_rank,cuda_visible_devices

rank="${SLURM_PROCID:-${RANK:-}}"
node="${SLURMD_NODENAME:-$(hostname -s)}"
local_rank="${SLURM_LOCALID:-${LOCAL_RANK:-0}}"
visible="${CUDA_VISIBLE_DEVICES:-}"

if [[ -z "${rank}" ]]; then
  echo "capture_rank_map.sh: SLURM_PROCID/RANK is not set" >&2
  exit 2
fi

escaped_visible=${visible//\"/\"\"}
printf '%s,%s,%s,"%s"\n' "${rank}" "${node}" "${local_rank}" "${escaped_visible}"

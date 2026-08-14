# Collecting Identity Artifacts

GPU Triage M4 uses a small set of artifacts to build identity relations without a hand-written graph.

## Why rank-map.csv exists

Slurm job metadata can identify the allocation and nodes, but the exact GPU used by an individual distributed process is runtime/launcher state. GPU Triage therefore treats `rank-map.csv` as a capture artifact, not as a configuration file.

A typical header is:

```csv
rank,node,local_rank,cuda_visible_devices
```

Run `scripts/capture_rank_map.sh` once per rank and aggregate its output.

## Slurm job

Capture a one-line job record:

```bash
scontrol show job -o "$SLURM_JOB_ID" > slurm-job.txt
```

GPU Triage currently consumes `JobId` and `NodeList` and keeps the rest as future adapter surface.

## NVIDIA GPU inventory

Prefer durable GPU UUID and PCI bus ID over a local GPU index.

A convenient collection command is:

```bash
host=$(hostname -s)
printf 'node,index,uuid,pci.bus_id\n' > nvidia-gpus.csv
nvidia-smi --query-gpu=index,uuid,pci.bus_id --format=csv,noheader,nounits \
  | sed "s/^/${host},/" >> nvidia-gpus.csv
```

## GPU-NIC topology

On NVIDIA versions that provide the focused command:

```bash
nvidia-smi topo -nic > nvidia-topo.txt
```

Fallback for older deployments:

```bash
nvidia-smi topo -m > nvidia-topo.txt
```

GPU Triage treats equally-near NIC/HCA candidates as ambiguous instead of guessing one.

## InfiniBand / HCA identity

`ib-devices.csv` uses:

```csv
node,ibdev,netdev,pci_bdf,guid,port
```

The current PoC expects this normalized artifact rather than depending on one vendor command's presentation format. A future collector will generate it directly from sysfs/rdma tooling.

## Important safety rule

Identity discovery is evidence scoping, not root-cause inference.

A PCIe device can be degraded and still be irrelevant to the affected workload. GPU Triage only allows hardware evidence to influence a hypothesis when the entity can be reconciled to the affected rank/job path. Unresolved and ambiguous links remain visible as evidence gaps.

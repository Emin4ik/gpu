# M8 Benchmark v0.2 — Source Manifest

Created: 2026-08-15

This benchmark version was assembled after M8.1 from public primary-source incident reports that were not used as the v0.1 frozen holdout. The engine is not changed after the v0.2 holdout freeze and before its first run.

## Composition

- 24 staged scenarios total
- 16 source incidents
- 8 adversarial/mutation scenarios derived from those source incidents
- 12 development scenarios
- 12 frozen holdout scenarios

The evaluator receives only the observations available at each stage. Source prose and later-stage facts are not passed to the engine.

## New source incidents

| Source ID | Primary source | Benchmark role |
|---|---|---|
| `pytorch-38174` | https://github.com/pytorch/pytorch/issues/38174 | uneven DDP inputs / collective-work mismatch |
| `pytorch-158719` | https://github.com/pytorch/pytorch/issues/158719 | FSDP parameters used differently across ranks |
| `nccl-2167` | https://github.com/NVIDIA/nccl/issues/2167 | NCCL release regression with known-good version control |
| `nccl-1876` | https://github.com/NVIDIA/nccl/issues/1876 | NCCL version/algorithm performance regression |
| `pytorch-175666` | https://github.com/pytorch/pytorch/issues/175666 | PyTorch/CUDA version memory regression |
| `nccl-1317` | https://github.com/NVIDIA/nccl/issues/1317 | NIC/link failure during NCCL test |
| `pytorch-24080` | https://github.com/pytorch/pytorch/issues/24080 | DataLoader pinned-memory CPU overhead / input-path bottleneck |
| `nccl-634` | https://github.com/NVIDIA/nccl/issues/634 | poorly functioning NCCL bootstrap IP interface |
| `pytorch-68726` | https://github.com/pytorch/pytorch/issues/68726 | hostname resolution to localhost breaks distributed group |
| `nccl-290` | https://github.com/NVIDIA/nccl/issues/290 | `/dev/shm` exhaustion during NCCL init |
| `nccl-875` | https://github.com/NVIDIA/nccl/issues/875 | connection-refused bootstrap/interface reachability |
| `nccl-1241` | https://github.com/NVIDIA/nccl/issues/1241 | duplicate GPU assignment between ranks |
| `pytorch-53658` | https://github.com/pytorch/pytorch/issues/53658 | NCCL barrier implicit device selection issue |
| `pytorch-109074` | https://github.com/pytorch/pytorch/issues/109074 | torch.compile/Triton GIL runtime deadlock |
| `pytorch-163546` | https://github.com/pytorch/pytorch/issues/163546 | rank desynchronization after CUDA OOM / watchdog deadlock |
| `nccl-tests-252` | https://github.com/NVIDIA/nccl-tests/issues/252 | ACS/GDR configuration failure mode |

## Benchmark discipline

Some sources map to a currently supported diagnostic domain; others intentionally represent unsupported runtime/bootstrap/resource classes where the correct v0.2 behavior is abstention. Mutation cases test negative evidence, hypothesis reversal, and completed-test memory introduced in M8.1.

Action-count and tool-transition fields remain curated replay proxies, not human wall-clock measurements.

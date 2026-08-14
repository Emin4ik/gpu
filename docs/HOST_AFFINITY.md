# Host IRQ / CPU affinity evidence

GPU Triage can correlate NIC interrupt placement with the CPU affinity of a communication process. This adapter exists for cases where distributed communication waits are visible while GPU kernel durations remain healthy.

The correlation is deliberately conservative. It does **not** infer IRQ interference from a busy host or from an IRQ label alone.

## Recognized artifacts

### `proc-interrupts.txt`

A snapshot of `/proc/interrupts`:

```bash
cat /proc/interrupts > proc-interrupts.txt
```

The parser records per-IRQ CPU counters, total interrupt activity, active CPUs, and the kernel IRQ label.

### `irq-affinity.csv`

Collected IRQ-to-device identity plus allowed/effective CPU affinity:

```bash
scripts/capture_irq_affinity.sh ens6f0 mlx5_4 > irq-affinity.csv
```

Format:

```csv
irq,cpu_list,effective_cpu_list,ibdev,netdev,pci_bdf
120,0-3,2,mlx5_4,ens6f0,0000:d1:00.0
```

`cpu_list` corresponds to the configured IRQ affinity. When `effective_cpu_list` is available it is preferred for overlap checks because the effective CPU set can be narrower than the configured set for managed interrupts.

### `process-affinity.csv`

A runtime capture for the communication process/thread associated with an affected rank:

```bash
scripts/capture_process_affinity.sh "$RANK" "$PID" nccl_comm > process-affinity.csv
```

Format:

```csv
rank,pid,role,cpu_list,node
0,4242,nccl_comm,2-3,gpu001
```

Roles containing `nccl`, `comm`, or `communication` are currently treated as communication-process evidence.

## Correlation rule

GPU Triage emits `irq_shares_nccl_cpu = true` only when all of the following are known:

1. the IRQ has non-zero activity in `/proc/interrupts`;
2. the IRQ identity maps unambiguously to an HCA/NIC on the affected rank path;
3. an affected-rank communication process has a known CPU affinity;
4. the effective IRQ CPU set (or configured set when no effective set is available) intersects the communication-process CPU set.

Example:

```text
affected rank 0
    -> HCA mlx5_4

IRQ 120
    -> mlx5_4
    -> active on CPU 2

rank 0 NCCL communication process
    -> allowed CPUs 2-3

intersection = {2}
    -> irq_shares_nccl_cpu = true
```

That evidence can move the existing `host_cpu_irq_interference` hypothesis from `supported` to `probable`. The next registered diagnostic is then a short CPU/kernel profile, which provides causal confirmation rather than relying on affinity overlap alone.

## Clean / missing evidence

If all comparable mappings are present but IRQ and process CPU sets do not overlap, the adapter emits `irq_affinity_clean = true`. In v0.1 this is preserved as evidence but is **not yet treated as proof that all host interference is absent**.

If process affinity, active IRQ state, or affected-HCA identity is missing, GPU Triage emits an evidence-gap warning and does not guess an overlap.

## Safety boundary

This adapter does not:

- assume an IRQ with `mlx5` in its label belongs to the affected HCA without identity evidence;
- treat configured IRQ affinity as actual servicing CPU when an effective affinity is available;
- infer contention merely because a process and IRQ are both on the same node;
- claim a confirmed root cause from affinity overlap alone;
- replace `perf`, eBPF, or a short CPU/kernel profile when deeper confirmation is needed.

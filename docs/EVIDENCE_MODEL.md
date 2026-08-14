# Evidence model

GPU Triage treats evidence as a collection of observations, not as a flat dictionary.

The measured entity is part of the fact:

```text
Observation(
  key="pcie_width",
  entity="pcie:0000:c1:00.0",
  value=8,
  source="lspci-full.txt",
  raw_ref="lspci-full.txt#0000:c1:00.0"
)
```

Two devices can therefore expose the same metric without overwriting each other:

```text
pcie_width @ pcie:0000:c1:00.0 = 16
pcie_width @ pcie:0000:e1:00.0 = 8
```

## Safety rules

1. Preserve same-key observations from different entities.
2. Pair related facts only when their entity matches.
3. If an affected workload path is known, remove hardware evidence outside that path before hypothesis evaluation.
4. Keep a raw artifact reference for traceability.

For example, `pcie_width=8` from GPU A must never be paired with `pcie_expected_width=16` from GPU B.

## M5 coverage

The current PoC supports multi-device evidence for:

- full or targeted `lspci -vv` output;
- multi-GPU `nvidia-smi -q` output when GPU UUIDs are present;
- multiple per-HCA counter artifacts;
- entity-aware baseline comparisons;
- affected-path filtering through the identity graph.

The parsers still extract facts only. They do not assign causal meaning.

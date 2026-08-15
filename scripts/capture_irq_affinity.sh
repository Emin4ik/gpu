#!/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <netdev> [ibdev]" >&2
  exit 2
fi

netdev=$1
ibdev=${2:-}
device_path=$(readlink -f "/sys/class/net/$netdev/device")
pci_bdf=$(basename "$device_path")
irq_dir="$device_path/msi_irqs"

printf 'irq,cpu_list,effective_cpu_list,ibdev,netdev,pci_bdf\n'
if [ ! -d "$irq_dir" ]; then
  exit 0
fi

for entry in "$irq_dir"/*; do
  [ -e "$entry" ] || continue
  irq=${entry##*/}
  allowed=$(cat "/proc/irq/$irq/smp_affinity_list" 2>/dev/null || true)
  effective=$(cat "/proc/irq/$irq/effective_affinity_list" 2>/dev/null || true)
  printf '%s,"%s","%s",%s,%s,%s\n' "$irq" "$allowed" "$effective" "$ibdev" "$netdev" "$pci_bdf"
done

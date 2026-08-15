from gputriage.parsers import parse_ib_counters, parse_lspci, parse_nccl_log, parse_nvidia_smi_q


def fact_map(observations):
    return {ob.key: ob.value for ob in observations}


def test_parse_lspci_link_width_and_speed():
    text = """
LnkCap: Port #0, Speed 32GT/s, Width x16, ASPM L1
LnkSta: Speed 32GT/s, Width x8
"""
    facts = fact_map(parse_lspci(text))
    assert facts["pcie_expected_width"] == 16
    assert facts["pcie_width"] == 8
    assert facts["pcie_expected_speed_gts"] == 32.0
    assert facts["pcie_speed_gts"] == 32.0


def test_parse_nvidia_smi_thermal_and_clock():
    text = """
Clocks
    Graphics : 1185 MHz
    SM : 1185 MHz
Temperature
    GPU Current Temp : 82 C
Clocks Event Reasons
    SW Thermal Slowdown : Active
    HW Thermal Slowdown : Not Active
"""
    facts = fact_map(parse_nvidia_smi_q(text))
    assert facts["gpu_sm_clock_mhz"] == 1185
    assert facts["gpu_temperature_c"] == 82
    assert facts["thermal_throttle_reason"] is True


def test_parse_nccl_transport_and_timeout():
    text = """
node:123:123 [0] NCCL INFO NET/Socket : Using [0]eth0:10.0.0.1<0>
Rank 3 Watchdog caught collective operation timeout
GDR disabled for this path
"""
    facts = fact_map(parse_nccl_log(text))
    assert facts["nccl_socket_transport"] is True
    assert facts["nccl_timeout_present"] is True
    assert facts["communication_waits"] is True
    assert facts["nccl_gdr_disabled"] is True
    assert facts["nccl_log_rank_count"] == 1


def test_parse_ib_counter_total():
    text = """
symbol_error_counter: 7
link_downed_counter: 1
port_xmit_data: 123456
"""
    facts = fact_map(parse_ib_counters(text))
    assert facts["fabric_error_counter_total"] == 8
    assert facts["ib_counter.symbol_error_counter"] == 7

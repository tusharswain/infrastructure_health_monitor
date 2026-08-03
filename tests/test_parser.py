"""Tests for the remote metric command parser."""
from __future__ import annotations

from inframon.collector.commands import parse_remote_output


SAMPLE_OUTPUT = """===CPU===
%Cpu(s): 10.0 us,  5.0 sy,  0.0 ni, 85.0 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
===MEM===
              total        used        free      shared  buff/cache   available
Mem:          16000        8000        2000         100        7000        7000
===DISK===
Filesystem     512-blocks      Used Available Capacity Mounted on
/dev/disk1s1  245000000 120000000 100000000    50%   /
===LOAD===
 12:00:00 up 10 days,  1:00,  2 users,  load average: 2.50, 3.00, 4.00
===ZOMBIE===
0
===NET1===
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1000       10    0    0    0     0          0         0 1000       10    0    0    0    0    0          0
  eth0: 5000       50    0    0    0     0          0         0 2000       20    0    0    0    0    0          0
===NET2===
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1000       10    0    0    0     0          0         0 1000       10    0    0    0    0    0          0
  eth0: 7000       70    0    0    0     0          0         0 3000       30    0    0    0    0    0          0
"""


def test_parse_remote_output():
    snapshot = parse_remote_output("test-node", SAMPLE_OUTPUT)
    assert snapshot.node == "test-node"
    assert abs(snapshot.cpu_percent - 15.0) < 0.01
    assert abs(snapshot.memory_percent - 50.0) < 0.01
    assert abs(snapshot.disk_percent - 50.0) < 0.01
    assert snapshot.load_1 == 2.5
    assert snapshot.load_5 == 3.0
    assert snapshot.load_15 == 4.0
    assert snapshot.zombie_count == 0
    assert snapshot.network_in_bytes == 2000
    assert snapshot.network_out_bytes == 1000


def test_parse_missing_sections():
    snapshot = parse_remote_output("empty-node", "===CPU===\n===MEM===\n===DISK===\n===LOAD===\n===ZOMBIE===\n===NET1===\n===NET2===")
    assert snapshot.node == "empty-node"
    assert snapshot.cpu_percent == 0.0
    assert snapshot.zombie_count == 0

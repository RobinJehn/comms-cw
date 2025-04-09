#!/usr/bin/env python3
"""
test_rst_packet.py – A test harness to exclusively test the NAT controller's RST behavior when the NAT table is full.

This script performs the following:
  - Phase 1: It "saturates" the NAT table by creating NUM_CONN connections from h2 to h1.
             Each connection uses a different server port on h1 (e.g., 50000, 50001, …).
             Packets are captured on h1 into /tmp/h1_saturate.pcap.
  - Phase 2: It then attempts one extra connection on a new port (e.g., 50010). With the NAT table saturated,
             this connection should be rejected—i.e. a TCP RST packet should be sent.
             The extra connection’s packets are captured into /tmp/h1_extra.pcap.

After each phase, the script uses h1 (the host that ran tcpdump) to read and print the capture output.

Before running, ensure your NAT controller (nat.py) is running (e.g., via “osken-manager nat.py”) and
that it is configured with a limited available port pool (e.g., 3 ports).

Usage:
    sudo python3 test_rst_packet.py
"""

from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.log import setLogLevel, info
import time
import threading
from threading import Lock

# Import your custom topology; nattopo.py must define the NatTopo class.
from nattopo import NatTopo

# A global lock to serialize client commands from h2 (when running in threads)
cmd_lock = Lock()


def show_pcap(host, pcap_file, label):
    """Run tcpdump on the given host to read the pcap file and print the output."""
    # Pause to allow file buffers to be flushed
    time.sleep(1)
    output = host.cmd("tcpdump -nr " + pcap_file)
    info("\n*** {} - {} ***\n{}".format(label, pcap_file, output))


def test_rst_packet(net):
    info("\n*** Starting RST test (simulate NAT table full) ***\n")
    h1 = net.get("h1")
    h2 = net.get("h2")
    h3 = net.get("h3")

    # Phase 1: Saturate the NAT table.
    saturate_pcap = "h1.pcap"
    info(
        "\n[Phase 1] Capturing saturating connections in {}...\n".format(saturate_pcap)
    )
    h1.cmd("tcpdump -w {} &".format(saturate_pcap))
    time.sleep(1)

    h1.cmd("nc -l 50000 &")
    h1.cmd("nc -l 50001 &")
    h2.cmd("echo 'Hello NAT' | nc h1 50000")
    h3.cmd("echo 'Hello NAT' | timeout 5 nc h1 50001")

    h2.cmd("pkill nc")
    h1.cmd("pkill nc")
    h1.cmd("pkill tcpdump")
    show_pcap(h1, saturate_pcap, "Saturating Connections")

    info("\n*** RST test completed ***\n")


if __name__ == "__main__":
    setLogLevel("info")
    info("Creating Mininet topology using nattopo...\n")
    topo = NatTopo()
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(name, ip="127.0.0.1", port=6653),
    )
    net.start()
    try:
        test_rst_packet(net)
    finally:
        info("Stopping Mininet...\n")
        net.stop()

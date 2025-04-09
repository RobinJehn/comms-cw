#!/usr/bin/env python3
"""
test_nat.py – A test harness to exercise the marking criteria:

1. Mediation of a TCP connection (flow installation)
2. Reuse of a client TCP port from an expired NAT table entry
3. Sending a TCP RST when the NAT table is full
4. Support for many simultaneous connections

Before running, make sure your NAT controller (nat.py) is running via:
    osken-manager nat.py

Usage:
    sudo python3 test_nat.py

This script starts a packet capture on h1 and after each test reads the capture
output from h1 (using "tcpdump -nr <pcapfile>") and prints it automatically.
A 10-second pause separates each test.
"""

from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.log import setLogLevel, info
import time
import threading

# Import your custom topology from nattopo.py (ensure it defines the NatTopo class)
from nattopo import NatTopo

# ---------------------------
# Helper functions for tests
# ---------------------------


def show_pcap(host, pcap_file, test_name):
    """Run tcpdump on 'host' to read the pcap file and print the output."""
    pcap_output = host.cmd("tcpdump -nr " + pcap_file)
    info(
        "\n*** {} pcap output from {} ***\n{}".format(test_name, pcap_file, pcap_output)
    )


def test_single_connection(net):
    """Test that a single NAT-mediated TCP connection is working (Criterion 1)."""
    info("\n*** Starting single connection test ***\n")
    h1 = net.get("h1")
    h2 = net.get("h2")
    pcap_file = "/tmp/h1_single.pcap"
    # Start a capture on h1 (saved to /tmp/h1_single.pcap)
    h1.cmd("tcpdump -w {} &".format(pcap_file))
    time.sleep(1)
    # Start a netcat listener on h1 on port 50000 (listener runs indefinitely)
    h1.cmd("netcat -l 50000 &")
    time.sleep(1)
    # Initiate connection from h2; wrap the netcat call with timeout so it auto-terminates.
    h2.cmd("echo 'Hello NAT' | timeout 5 netcat 10.0.1.100 50000")
    time.sleep(1)
    # Stop the listener and tcpdump on h1
    h1.cmd("pkill tcpdump")
    h1.cmd("pkill netcat")
    # Read and print the capture file using h1
    show_pcap(h1, pcap_file, "Single Connection Test")
    time.sleep(10)


def test_port_reuse(net):
    """
    Test that after a NAT entry expires, the public port is reused (Criterion 2).
    Establish one connection, wait for the NAT entry to expire, and then establish a new connection.
    """
    info("\n*** Starting port reuse test ***\n")
    h1 = net.get("h1")
    h2 = net.get("h2")
    pcap_file = "/tmp/h1_reuse.pcap"
    h1.cmd("tcpdump -w {} &".format(pcap_file))
    # Start a listener on h1 without timeout.
    h1.cmd("nc -l 50000 &")
    time.sleep(1)
    # Establish first connection from h2.
    h2.cmd("echo 'First connection' | timeout 5 nc 10.0.1.100 50000")
    h1.cmd("pkill nc")
    info("Waiting for NAT entry to expire...\n")
    time.sleep(12)
    # Establish second connection from h2.
    h1.cmd("nc -l 50000 &")
    time.sleep(1)
    h2.cmd("echo 'Second connection' | timeout 5 nc 10.0.1.100 50000")
    h1.cmd("pkill nc")
    h1.cmd("pkill tcpdump")
    show_pcap(h1, pcap_file, "Port Reuse Test")
    time.sleep(10)


def test_rst_on_table_full(net):
    """
    Test that if the NAT table is full, a new connection triggers a TCP RST (Criterion 3).
    For testing, assume your NAT controller limits the available port pool to a small number (e.g., 3 ports).
    """
    info("\n*** Starting RST test (simulate NAT table full) ***\n")
    h1 = net.get("h1")
    h2 = net.get("h2")
    pcap_file = "/tmp/h1_rst.pcap"
    h1.cmd("tcpdump -w {} &".format(pcap_file))
    NUM_CONN = (
        3  # Adjust your NAT controller to provide a small number of available ports.
    )
    conn_threads = []

    def make_connection(conn_id):
        info("Starting connection " + str(conn_id) + "\n")
        h1.cmd("nc -l 50000 &")
        time.sleep(0.5)
        h2.cmd("echo 'Connection {}' | timeout 5 nc 10.0.1.100 50000".format(conn_id))
        h1.cmd("pkill nc")

    # Saturate the NAT table with NUM_CONN connections.
    for i in range(NUM_CONN):
        t = threading.Thread(target=make_connection, args=(i,))
        conn_threads.append(t)
        t.start()
        time.sleep(0.2)
    for t in conn_threads:
        t.join()

    info("Now attempting one extra connection which should trigger a RST\n")
    h2.cmd("echo 'Extra connection' | timeout 5 nc 10.0.1.100 50000")
    time.sleep(1)
    h1.cmd("pkill tcpdump")
    show_pcap(h1, pcap_file, "RST Test")
    time.sleep(10)


def test_mass_connections(net):
    """
    Test support for many simultaneous connections (Criterion 4).
    Adjust NUM_CONN if hardware/VM resources are limited.
    """
    info("\n*** Starting mass connections test ***\n")
    h1 = net.get("h1")
    h2 = net.get("h2")
    pcap_file = "/tmp/h1_mass.pcap"
    h1.cmd("tcpdump -w {} &".format(pcap_file))
    NUM_CONN = 100  # Increase this number as permitted.
    threads = []

    def do_connection(conn_id):
        h1.cmd("nc -l 50000 &")
        time.sleep(0.05)
        h2.cmd(
            "echo 'Mass test connection {}' | timeout 5 nc 10.0.1.100 50000".format(
                conn_id
            )
        )
        h1.cmd("pkill nc")

    for i in range(NUM_CONN):
        t = threading.Thread(target=do_connection, args=(i,))
        threads.append(t)
        t.start()
        time.sleep(0.01)
    for t in threads:
        t.join()
    h1.cmd("pkill tcpdump")
    show_pcap(h1, pcap_file, "Mass Connections Test")
    time.sleep(10)


# ---------------------------
# Main test harness
# ---------------------------
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
        test_single_connection(net)
        test_port_reuse(net)
        test_rst_on_table_full(net)
        test_mass_connections(net)
    finally:
        info("Stopping Mininet...\n")
        net.stop()

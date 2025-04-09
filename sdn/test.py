#!/usr/bin/env python3
"""
test_nat.py – A test harness to exercise the marking criteria:

1. Mediation of a TCP connection (flow installation)
2. Reuse of a client TCP port from an expired NAT table entry
3. Sending a TCP RST when the NAT table is full
4. Support for many simultaneous connections

Before running, make sure your NAT controller (nat.py) is running via:
    osken-manager nat.py

And that your Mininet VM has the Python Mininet API installed.
"""

from mininet.net import Mininet
from mininet.topo import SingleSwitchTopo
from mininet.node import RemoteController
from mininet.log import setLogLevel, info
import time
import threading

# ---------------------------
# Helper functions for tests
# ---------------------------


def test_single_connection(net):
    """Test that a single TCP connection is mediated by NAT (Criterion 1)."""
    info("\n*** Starting single connection test\n")
    h1 = net.get("h1")
    h2 = net.get("h2")
    # Start a capture on h1 (optional – you can check your capture files manually)
    h1.cmd("tcpdump -w /tmp/h1.pcap &")
    time.sleep(1)
    # Start a listener on h1 on port 50000
    h1.cmd("nc -l 50000 &")
    time.sleep(1)
    # Initiate connection from h2
    result = h2.cmd("echo 'Hello NAT' | nc 10.0.1.100 50000")
    info("Single connection result: " + result + "\n")
    time.sleep(1)
    # Clean up
    h1.cmd("pkill tcpdump")
    h1.cmd("pkill nc")
    time.sleep(1)
    info("*** Single connection test completed\n")


def test_port_reuse(net):
    """
    Test that after a NAT table entry expires, the public port is reused (Criterion 2).
    We simulate this by creating a connection, waiting longer than the timeout, then creating a new one.
    """
    info("\n*** Starting port reuse test\n")
    h1 = net.get("h1")
    h2 = net.get("h2")
    # Start a listener on h1 and connect from h2
    h1.cmd("nc -l 50000 &")
    time.sleep(1)
    h2.cmd("echo 'First connection' | nc 10.0.1.100 50000")
    # Wait longer than the NAT entry timeout (assumed to be 10 sec)
    info("Waiting for NAT entry to expire...\n")
    time.sleep(12)
    # Initiate a new connection from h2
    result = h2.cmd("echo 'Second connection' | nc 10.0.1.100 50000")
    info("Second connection result: " + result + "\n")
    # Clean up
    h1.cmd("pkill nc")
    time.sleep(1)
    info("*** Port reuse test completed\n")


def test_rst_on_table_full(net):
    """
    Test that if the NAT table is full, a new connection triggers a TCP RST (Criterion 3).
    For testing purposes you can either:
      - Temporarily restrict the available ports in your NAT controller.
      - Or, open a number of simultaneous connections to saturate the available NAT entries.
    In this test, we simulate a full table by assuming the NAT controller's available port pool is reduced.
    """
    info("\n*** Starting RST test (simulate NAT table full)\n")
    h1 = net.get("h1")
    h2 = net.get("h2")
    # For testing, assume you have set a small number of available ports in your NAT controller (e.g. 3).
    NUM_CONN = 3  # Adjust this in your controller for testing if needed.
    conn_threads = []

    def make_connection(conn_id):
        info("Starting connection " + str(conn_id) + "\n")
        h1.cmd("nc -l 50000 &")
        time.sleep(0.5)
        out = h2.cmd("echo 'Connection {}' | nc 10.0.1.100 50000".format(conn_id))
        info("Connection {} result: {}\n".format(conn_id, out))
        h1.cmd("pkill nc")

    # Saturate the NAT table:
    for i in range(NUM_CONN):
        t = threading.Thread(target=make_connection, args=(i,))
        conn_threads.append(t)
        t.start()
        time.sleep(0.2)

    for t in conn_threads:
        t.join()

    info("Now attempting one extra connection which should trigger a RST\n")
    extra_result = h2.cmd("echo 'Extra connection' | nc 10.0.1.100 50000")
    info("Extra connection result (expected to be rejected): " + extra_result + "\n")
    info("*** RST test completed\n")


def test_mass_connections(net):
    """
    Test support for many simultaneous connections (Criterion 4).
    You may simulate this with a lower number (e.g. 100) if your environment is limited.
    """
    info("\n*** Starting mass connections test\n")
    h1 = net.get("h1")
    h2 = net.get("h2")
    NUM_CONN = 100  # Increase this number if your system permits.
    threads = []

    def do_connection(conn_id):
        h1.cmd("nc -l 50000 &")
        time.sleep(0.05)
        out = h2.cmd(
            "echo 'Mass test connection {}' | nc 10.0.1.100 50000".format(conn_id)
        )
        info("Mass connection {} result: {}\n".format(conn_id, out))
        h1.cmd("pkill nc")

    for i in range(NUM_CONN):
        t = threading.Thread(target=do_connection, args=(i,))
        threads.append(t)
        t.start()
        time.sleep(0.01)

    for t in threads:
        t.join()

    info("*** Mass connections test completed\n")


# ---------------------------
# Main test harness
# ---------------------------
if __name__ == "__main__":
    setLogLevel("info")
    info("Creating Mininet topology...\n")
    # Create a simple topology with one switch and 3 hosts (h1, h2, h3)
    topo = SingleSwitchTopo(k=3)
    # Connect to a remote controller (make sure its IP/port match your NAT controller)
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

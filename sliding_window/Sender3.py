# Robin Jehn s2024553

import sys
import socket
import struct
import threading
import time
import os
import math
from utils import log, SequenceNumber

LOCK = threading.Lock()
BASE = 0  # Last unacknowledged package
NEXT_SEQ_NUM = SequenceNumber()  # First unused sequence number
TIMER = None
PACKETS_IN_TRANSIT = {}  # maps sequence id to packet for all in-transit packet
PACKET_SIZE = 1024
TOTAL_PACKETS = 0
S = None

# One thread to send, one thread to receive the acknowledgements.
# Shared state of what has been acknowledged so far, sender only sends next packet if with in the window
# We resend all packages at once if the oldest packet that hasn't been acknowledged timed out.


def timeout():
    global S, PACKETS_IN_TRANSIT
    # Resend all in-transit packets
    log("Timeout")
    with LOCK:
        if not S:
            raise ValueError("Socket not defined")
        for data in PACKETS_IN_TRANSIT.values():
            S.sendall(data)
        start_timer()


def start_timer():
    global TIMER
    if TIMER:
        TIMER.cancel()
    TIMER = threading.Timer(RETRY_TIMEOUT, timeout)
    TIMER.start()


def stop_timer():
    global TIMER
    if TIMER:
        TIMER.cancel()


def remove_from_transit(ack_seq_num: int):
    """
    Only keep packets that have a sequence number higher then the last acknowledged one
    """
    global PACKETS_IN_TRANSIT
    PACKETS_IN_TRANSIT = {
        k: v for k, v in PACKETS_IN_TRANSIT.items() if k > ack_seq_num
    }


def handle_acknowledgments():
    global BASE, S, NEXT_SEQ_NUM
    with LOCK:
        if not S:
            raise ValueError("Socket not defined")
    while True:
        ack_data = S.recv(2)
        ack_seq_num = struct.unpack("!H", ack_data)[0]
        with LOCK:
            # Ignore old acknowledgments
            if ack_seq_num < BASE:
                continue
            remove_from_transit(ack_seq_num)
            BASE = ack_seq_num + 1
            if NEXT_SEQ_NUM() == BASE:
                # Stop timer as every packet has been received
                stop_timer()
            else:
                # Restart timer
                start_timer()
            # End if all packets have been acknowledged
            if BASE >= TOTAL_PACKETS:  # Base is 0 indexed
                break


def send_packet(data: bytes, eof_flag: bool, window_size: int):
    global S, NEXT_SEQ_NUM
    with LOCK:
        if not S:
            raise ValueError("Socket not defined")
    # Wait until we have gotten acknowledgments
    while True:
        with LOCK:
            if NEXT_SEQ_NUM() < BASE + window_size:
                break
        # Avoid full cpu usage
        time.sleep(0.01)

    with LOCK:
        # Build packet
        if NEXT_SEQ_NUM() == BASE:
            start_timer()
        header = struct.pack("!HB", NEXT_SEQ_NUM(), eof_flag)
        packet = header + data

        # Send packet
        PACKETS_IN_TRANSIT[NEXT_SEQ_NUM()] = packet
        S.sendall(packet)
        NEXT_SEQ_NUM.next()


def send_file(filename: str, window_size: int):
    global TOTAL_PACKETS, PACKET_SIZE
    TOTAL_PACKETS = math.ceil(os.path.getsize(filename) / PACKET_SIZE)
    log(f"Total packets: {TOTAL_PACKETS}")
    with open(filename, "rb") as f:
        send_packets = 0
        while send_packets < TOTAL_PACKETS:
            # We cannot just check the size of the data returned by read to determine whether we are at the end of a file because the size might be a multiple of PACKAGE_SIZE
            data = f.read(PACKET_SIZE)
            # +1 for the packet to be sent
            eof_flag = send_packets + 1 == TOTAL_PACKETS
            send_packet(data, eof_flag, window_size)
            send_packets += 1


if __name__ == "__main__":
    remote_host = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    RETRY_TIMEOUT = int(sys.argv[4]) / 1000
    window_size = int(sys.argv[5])
    S = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    S.connect((remote_host, port))
    ack_thread = threading.Thread(target=handle_acknowledgments)
    ack_thread.start()

    start_time = time.time()
    send_file(filename, window_size)
    time_taken = time.time() - start_time
    throughput = int(os.path.getsize(filename) / time_taken / 1024)
    print(f"{throughput}")

    ack_thread.join()
    S.close()

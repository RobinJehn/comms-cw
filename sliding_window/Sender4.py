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
NEXT_SEQ_NUM = SequenceNumber()  # First unused sequence number
TIMER = None
PACKETS_IN_TRANSIT = (
    {}
)  # maps sequence id to (time_stamp, packet) for all in-transit packet
PACKET_SIZE = 1024
TOTAL_PACKETS = 0
S = None
HIGHEST_ACK = -1  # The higest sequence number we have an acknowledgment for
DONE = False  # Flag set to true when all packages have been acknowledged


def base() -> int:
    """
    Returns the lowest not yet acknowledged sequence number.
    Needs a lock around
    """
    if len(PACKETS_IN_TRANSIT) == 0:
        return HIGHEST_ACK + 1
    return min(PACKETS_IN_TRANSIT.keys())


def resend_timedout_packets(retry_timeout_s: int, sock: socket.socket):
    """
    Resend all the packets that are timedout.
    This function is called in a thread
    """
    while True:
        with LOCK:
            # We are done
            if DONE:
                break

            for seq_num, (time_stamp, packet) in PACKETS_IN_TRANSIT.items():
                if retry_timeout_s < time.time() - time_stamp:
                    sock.sendall(packet)
                    log(f"Resend packet: {seq_num}")
                    PACKETS_IN_TRANSIT[seq_num] = (time.time(), packet)
        time.sleep(0.1)


def handle_acknowledgments():
    global S, NEXT_SEQ_NUM, HIGHEST_ACK, DONE
    with LOCK:
        if not S:
            raise ValueError("Socket not defined")
    while True:
        ack_data = S.recv(2)
        ack_seq_num = struct.unpack("!H", ack_data)[0]
        with LOCK:
            # Ignore old acknowledgments
            if ack_seq_num < base():
                continue
            PACKETS_IN_TRANSIT.pop(ack_seq_num)
            HIGHEST_ACK = max(HIGHEST_ACK, ack_seq_num)

            # End if all packets have been acknowledged
            if base() >= TOTAL_PACKETS:  # Base is 0 indexed
                DONE = True
                break


def send_packet(data: bytes, eof_flag: bool, window_size: int):
    global S, NEXT_SEQ_NUM
    with LOCK:
        if not S:
            raise ValueError("Socket not defined")
    # Wait until we have gotten acknowledgments
    while True:
        with LOCK:
            if NEXT_SEQ_NUM() < base() + window_size:
                break
        # Avoid full cpu usage
        time.sleep(0.1)
        log(f"Waiting for {NEXT_SEQ_NUM()}")

    with LOCK:
        # Build packet
        header = struct.pack("!HB", NEXT_SEQ_NUM(), eof_flag)
        packet = header + data

        # Send packet
        PACKETS_IN_TRANSIT[NEXT_SEQ_NUM()] = (time.time(), packet)
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
    retry_timeout_s = int(sys.argv[4]) / 1000  # The arg is given in ms
    window_size = int(sys.argv[5])
    S = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    S.connect((remote_host, port))
    ack_thread = threading.Thread(target=handle_acknowledgments)
    resend_thread = threading.Thread(
        target=resend_timedout_packets, args=(retry_timeout_s, S)
    )
    ack_thread.start()
    resend_thread.start()

    start_time = time.time()
    send_file(filename, window_size)
    time_taken = time.time() - start_time
    throughput = int(os.path.getsize(filename) / time_taken / 1024)
    print(f"{throughput}")

    resend_thread.join()
    ack_thread.join()
    S.close()

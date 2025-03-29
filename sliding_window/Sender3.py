# Robin Jehn s2024553

import sys
import socket
import struct
import threading
import time
import os
import math
from utils import log, SequenceNumber, PACKET_SIZE, send_file, HEADER_FORMAT


class GoBackN:
    def __init__(
        self,
        host: str,
        port: int,
        retry_timeout_ms: int,
        window_size: int,
        total_packets: int,
    ):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.connect((host, port))
        self.retry_timeout_s = retry_timeout_ms / 1000
        self.sock.settimeout(self.retry_timeout_s)
        self.window_size = window_size
        self.lock = threading.Lock()
        self.base = 0
        self.seq_num = SequenceNumber()
        self.packets_in_transit = {}
        self.timer = None
        self.total_packets = total_packets
        self.done = False

    def start_timer(self):
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(self.retry_timeout_s, self.timeout_event)
        self.timer.start()

    def stop_timer(self):
        if self.timer:
            self.timer.cancel()
        self.timer = None

    def timeout_event(self):
        # Resend all in-transit packets
        log("Timeout")
        with self.lock:
            for data in self.packets_in_transit.values():
                try:
                    self.sock.sendall(data)
                except ConnectionRefusedError as e:
                    with self.lock:
                        self.done = True
            self.start_timer()

    def remove_from_transit(self, ack_seq_num: int):
        """
        Only keep packets that have a sequence number higher then the last acknowledged one
        """
        self.packets_in_transit = {
            k: v for k, v in self.packets_in_transit.items() if k > ack_seq_num
        }

    def send(self, data: bytes, eof_flag: bool) -> bool:
        # Wait until we have gotten acknowledgments
        while True:
            with self.lock:
                if self.seq_num() < self.base + window_size:
                    break
            # Avoid full cpu usage
            time.sleep(0.01)

        with self.lock:
            # Build packet
            if self.seq_num() == self.base:
                self.start_timer()
            log(f"{self.seq_num()}")
            header = struct.pack(HEADER_FORMAT, self.seq_num(), eof_flag)
            packet = header + data

            # Send packet
            self.packets_in_transit[self.seq_num()] = packet
            self.sock.sendall(packet)
            self.seq_num.next()
        return True

    def handle_acknowledgments(self):
        while True:
            with self.lock:
                if self.done:
                    break

            try:
                ack_data = self.sock.recv(2)
            except socket.timeout:
                pass
            ack_seq_num = struct.unpack("!H", ack_data)[0]
            with self.lock:
                # Ignore old acknowledgments
                if ack_seq_num < self.base:
                    continue
                self.remove_from_transit(ack_seq_num)
                self.base = ack_seq_num + 1
                if self.seq_num() == self.base:
                    # Stop timer as every packet has been received
                    self.stop_timer()
                else:
                    # Restart timer
                    self.start_timer()
                # End if all packets have been acknowledged
                if self.base >= self.total_packets:  # Base is 0 indexed
                    break

    def __del__(self):
        self.sock.close()


if __name__ == "__main__":
    remote_host = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    retry_timeout_ms = int(sys.argv[4])
    window_size = int(sys.argv[5])

    total_packets = math.ceil(os.path.getsize(filename) / PACKET_SIZE)
    sender = GoBackN(
        remote_host,
        port,
        retry_timeout_ms,
        window_size,
        total_packets,
    )

    ack_thread = threading.Thread(target=sender.handle_acknowledgments)
    ack_thread.start()

    start_time = time.time()
    send_file(filename, sender)
    time_taken = time.time() - start_time
    throughput = int(os.path.getsize(filename) / time_taken / 1024)
    print(f"{throughput}")

    ack_thread.join()
    sender.sock.close()

# Robin Jehn s2024553

import sys
import socket
import struct
import threading
import time
import os
import math
from utils import log, SequenceNumber, PACKET_SIZE, send_file


class SlidingWindow:
    def __init__(self, host: str, port: int, window_size: int, total_packets: int):
        self.total_packets = total_packets
        self.window_size = window_size
        self.lock = threading.Lock()
        self.seq_num = SequenceNumber()
        self.packets_in_transit = {}
        self.highest_ack = -1
        self.socekt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.connect((host, port))

    def base(self) -> int:
        """
        Returns the lowest not yet acknowledged sequence number.
        Needs a lock around
        """
        if len(self.packets_in_transit) == 0:
            return self.highest_ack + 1
        return min(self.packets_in_transit.keys())

    def resend_timedout_packets(self):
        """
        Resend all the packets that are timedout.
        This function is called in a thread
        """
        while True:
            with self.lock:
                # We are done
                if self.base() >= self.total_packets:
                    break

                for seq_num, (time_stamp, packet) in self.packets_in_transit.items():
                    if retry_timeout_s < time.time() - time_stamp:
                        self.sock.sendall(packet)
                        log(f"Resend packet: {seq_num}")
                        self.packets_in_transit[seq_num] = (time.time(), packet)
            time.sleep(0.1)

    def handle_acknowledgments(self):
        while True:
            ack_data = self.sock.recv(2)
            ack_seq_num = struct.unpack("!H", ack_data)[0]
            with self.lock:
                # Ignore old acknowledgments
                if ack_seq_num < self.base():
                    continue
                self.packets_in_transit.pop(ack_seq_num)
                self.highest_ack = max(self.highest_ack, ack_seq_num)

                # End if all packets have been acknowledged
                if self.base() >= self.total_packets:  # Base is 0 indexed
                    break

    def send(self, data: bytes, eof_flag: bool) -> bool:
        # Wait until we have gotten acknowledgments
        while True:
            with self.lock:
                if self.seq_num() < self.base() + window_size:
                    break
            # Avoid full cpu usage
            time.sleep(0.1)
            log(f"Waiting for {self.seq_num()}")

        with self.lock:
            # Build packet
            header = struct.pack("!HB", self.seq_num(), eof_flag)
            packet = header + data

            # Send packet
            self.packets_in_transit[self.seq_num()] = (time.time(), packet)
            self.socket.sendall(packet)
            self.seq_num.next()
        return True


if __name__ == "__main__":
    remote_host = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    retry_timeout_s = int(sys.argv[4]) / 1000  # The arg is given in ms
    window_size = int(sys.argv[5])

    total_packets = math.ceil(os.path.getsize(filename) / PACKET_SIZE)
    sender = SlidingWindow(remote_host, port, window_size, total_packets)

    ack_thread = threading.Thread(target=sender.handle_acknowledgments)
    resend_thread = threading.Thread(target=sender.resend_timedout_packets)
    ack_thread.start()
    resend_thread.start()

    start_time = time.time()
    send_file(filename, sender)
    time_taken = time.time() - start_time
    throughput = int(os.path.getsize(filename) / time_taken / 1024)
    print(f"{throughput}")

    resend_thread.join()
    ack_thread.join()

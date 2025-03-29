# Robin Jehn s2024553

import sys
import socket
import struct
import time
import os
from utils import SequenceNumber, log, send_file, HEADER_FORMAT


class StopAndWait:
    def __init__(self, host: str, port: int, retry_timeout_ms: int):
        # Usually it should be limited to 2
        self.seq_num = SequenceNumber()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.connect((host, port))
        self.sock.settimeout(retry_timeout_ms / 1000)
        self.total_retransmissions = 0
        self.packet_retry_limit = 1000

    def send(self, data: bytes, eof_flag: bool) -> bool:
        """
        Params:
            data: The data to send
            eof_flag: A flag indicating if this is the last packet
        Returns:
            True if the packet was sent successfully, False otherwise
        """
        # Create the packet
        header = struct.pack(HEADER_FORMAT, self.seq_num(), eof_flag)
        packet = header + data

        # Send the packet
        success = self.send_packet_with_retry(packet)
        self.seq_num.next()
        return success

    def send_packet_with_retry(self, packet: bytes) -> bool:
        start_retry_amount = self.total_retransmissions
        while start_retry_amount + self.packet_retry_limit > self.total_retransmissions:
            try:
                self.sock.sendall(packet)
                # Wait for acknowledgment and verify that it matches the seq_num
                ack_data = self.sock.recv(2)
                ack_seq_num = struct.unpack("!H", ack_data)[0]
                if ack_seq_num == self.seq_num():
                    return True
                else:
                    log(f"Received wrong ack: {ack_seq_num}")
                    self.total_retransmissions += 1
                    pass
            except socket.timeout:
                self.total_retransmissions += 1
                log(f"Retransmission: {self.total_retransmissions}")
            except ConnectionRefusedError as e:
                self.total_retransmissions += 1
                log(f"Connection refused: {e}")

        return False

    def __del__(self):
        self.sock.close()


if __name__ == "__main__":
    remoteHost = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    retry_timeout_ms = int(sys.argv[4])

    sender = StopAndWait(remoteHost, port, retry_timeout_ms)
    start_time = time.time()
    send_file(filename, sender)
    time_took = time.time() - start_time
    throughput = int(os.path.getsize(filename) / time_took / 1024)
    print(f"{sender.total_retransmissions} {throughput}")
    sender.sock.close()

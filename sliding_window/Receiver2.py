# Robin Jehn s2024553

import sys
import socket
import struct
from typing import IO
from utils import PACKET_SIZE, HEADER_SIZE, log, SequenceNumber, HEADER_FORMAT


def receive_packets(port: int, file: IO):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("0.0.0.0", port))
        exp_seq_num = SequenceNumber(2)
        while True:
            packet, address = sock.recvfrom(PACKET_SIZE + HEADER_SIZE)
            seq_num, eof_flag = struct.unpack(HEADER_FORMAT, packet[:HEADER_SIZE])

            ack_packet = struct.pack("!H", seq_num)
            sock.sendto(ack_packet, address)

            if seq_num != exp_seq_num():
                log(f"Wrong sequence number: {seq_num}")
                continue

            data = packet[HEADER_SIZE:]
            file.write(data)
            if eof_flag:
                break
            exp_seq_num.next()


def receive_file(filename: str, port: int):
    with open(filename, "wb") as f:
        receive_packets(port, f)


if __name__ == "__main__":
    port = int(sys.argv[1])
    filename = sys.argv[2]

    receive_file(filename, port)

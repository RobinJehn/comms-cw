# Robin Jehn s2024553

import sys
import socket
import struct
from typing import IO
from utils import PACKET_SIZE, HEADER_SIZE, HEADER_FORMAT


def receive_packets(port: int, file: IO):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("0.0.0.0", port))
        while True:
            packet = s.recv(PACKET_SIZE + HEADER_SIZE)
            _, eof_flag = struct.unpack(HEADER_FORMAT, packet[:HEADER_SIZE])
            data = packet[HEADER_SIZE:]
            file.write(data)
            if eof_flag:
                break


def receive_file(filename: str, port: int):
    with open(filename, "wb") as f:
        receive_packets(port, f)


if __name__ == "__main__":
    port = int(sys.argv[1])
    filename = sys.argv[2]

    receive_file(filename, port)

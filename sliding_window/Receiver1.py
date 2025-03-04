# Robin Jehn s2024553

import sys
import socket
import struct
from typing import IO

def receive_packets(port: int, file: IO):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("0.0.0.0", port))
        while True:
            packet = s.recv(1027)
            seq_num, eof_flag = struct.unpack("!HB", packet[:3])
            data = packet[3:]
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

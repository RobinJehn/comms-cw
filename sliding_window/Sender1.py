# Robin Jehn s2024553

import sys
import socket
import struct
import os
import math
from utils import SequenceNumber, PACKET_SIZE


def send_file(filename: str, host: str, port: int):
    file_size = os.path.getsize(filename)
    total_packets = math.ceil(file_size / PACKET_SIZE)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s, open(
        filename, "rb"
    ) as f:
        s.connect((host, port))

        seq_num = SequenceNumber()
        while True:
            # Get the data
            data = f.read(PACKET_SIZE)
            eof_flag = seq_num() == total_packets - 1  # -1 because seq_num starts at 0

            # Create the packet
            header = struct.pack("!HB", seq_num(), eof_flag)
            packet = header + data

            # Send the packet
            s.sendall(packet)

            if eof_flag:
                break

            seq_num.next()


if __name__ == "__main__":
    remoteHost = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]

    send_file(filename, remoteHost, port)

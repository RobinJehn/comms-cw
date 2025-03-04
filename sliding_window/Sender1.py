# Robin Jehn s2024553

import sys
import socket
import struct
import select

PACKAGE_SIZE = 1024


def send_file(filename: str, host: str, port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s, open(
        filename, "rb"
    ) as f:
        s.connect((host, port))

        sequence_number = 0
        while True:
            # Get the data
            data = f.read(PACKAGE_SIZE)
            eof_flag = 1 if len(data) < PACKAGE_SIZE else 0

            # Create the packet
            header = struct.pack("!HB", sequence_number, eof_flag)
            packet = header + data

            # Send the packet
            s.sendall(packet)

            if eof_flag:
                break

            sequence_number += 1


if __name__ == "__main__":
    remoteHost = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]

    send_file(filename, remoteHost, port)

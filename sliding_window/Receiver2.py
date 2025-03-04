# Robin Jehn s2024553

import sys
import socket
import struct
from typing import IO

def receive_packets(port: int, file: IO):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("0.0.0.0", port))
        exp_seq_num = 0
        while True:
            packet, address = s.recvfrom(1027)
            seq_num, eof_flag = struct.unpack("!HB", packet[:3])

            ack_packet = struct.pack("!H", seq_num)
            s.sendto(ack_packet, address)

            if seq_num != exp_seq_num:
            #   print(f"Wrong sequence number: {seq_num}")
                continue
            
            data = packet[3:]
            file.write(data)
            if eof_flag:
                break
            exp_seq_num = (exp_seq_num + 1) % 2

def receive_file(filename: str, port: int):
    with open(filename, "wb") as f:
        receive_packets(port, f)


if __name__ == "__main__":
    port = int(sys.argv[1])
    filename = sys.argv[2]

    receive_file(filename, port)

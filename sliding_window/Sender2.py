# Robin Jehn s2024553

import sys
import socket
import struct
import time
import os

PACKAGE_SIZE = 1024


def send_packet_with_retry(
    sock: socket.socket, packet: bytes, retry_timeout_ms: int, seq_num: int
) -> int:
    attempts = 0
    while True:
        sock.sendall(packet)
        try:
            # Wait for acknowledgment and verify that it matches the seq_num
            ack_data = sock.recv(2)
            ack_seq_num = struct.unpack("!H", ack_data)[0]
            if ack_seq_num == seq_num:
                break
            else:
                # print(f"Wrong sequence number: {ack_seq_num}")
                pass
        except socket.timeout:
            attempts += 1
            # print(f"Attempt {attempts}")
    return attempts


def send_file(filename: str, host: str, port: int, retry_timeout_ms: int):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s, open(
        filename, "rb"
    ) as f:
        s.settimeout(retry_timeout_ms / 1000)
        s.connect((host, port))
        seq_num = 0
        total_attempts = 0
        start_time = time.time()
        while True:
            # Get the data
            data = f.read(PACKAGE_SIZE)
            eof_flag = 1 if len(data) < PACKAGE_SIZE else 0

            # Create the packet
            header = struct.pack("!HB", seq_num, eof_flag)
            packet = header + data

            # Send the packet
            total_attempts += send_packet_with_retry(
                s, packet, retry_timeout_ms, seq_num
            )

            if eof_flag:
                break

            seq_num = (seq_num + 1) % 2
    file_size = os.path.getsize(filename)
    time_took = time.time() - start_time
    throughput = int(file_size / time_took / 1024)
    print(f"{total_attempts} {throughput}")


if __name__ == "__main__":
    remoteHost = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    retry_timeout_ms = int(sys.argv[4])

    send_file(filename, remoteHost, port, retry_timeout_ms)

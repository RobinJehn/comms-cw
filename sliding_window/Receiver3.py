# Robin Jehn s2024553

import sys
import socket
import struct
import threading
from utils import log, PACKET_SIZE, HEADER_SIZE, HEADER_FORMAT


LOCK = threading.Lock()
BASE = 0  # Expected sequence number of the next in-order packet
S = None
OUTPUT_FILE = None


def send_ack(sock: socket.socket, addr: str):
    """Send an acknowledgment for a received packet. Acknowledging a sequence number also acknowledges all previous once."""
    ack_packet = struct.pack("!H", BASE - 1)
    sock.sendto(ack_packet, addr)
    log(f"Ack: {BASE - 1}")


def receive_packets():
    """Receives packets and writes them in order to the output file."""
    global BASE, S, BUFFER, OUTPUT_FILE
    with LOCK:
        if S is None:
            raise ValueError("Socket not initialized")
        if OUTPUT_FILE is None:
            raise ValueError("File not open")

    while True:
        log("in loop")
        packet, addr = S.recvfrom(PACKET_SIZE + HEADER_SIZE)
        if not packet:
            continue

        # Extract the sequence number and EOF flag
        seq_num, eof_flag = struct.unpack(HEADER_FORMAT, packet[:HEADER_SIZE])
        data = packet[HEADER_SIZE:]
        log(f"eof_flag: {eof_flag}")

        with LOCK:
            if seq_num < BASE:
                send_ack(S, addr)
                log("seq_num < BASE")
                continue

            log(f"seq_num {seq_num}=={BASE} BASE")
            if seq_num == BASE:
                # Write data to the file
                OUTPUT_FILE.write(data)
                BASE += 1
                send_ack(S, addr)

                # If EOF flag is set, stop receiving
                if eof_flag:
                    log("End of file reached")
                    break

    # Close everything
    S.close()
    OUTPUT_FILE.close()


if __name__ == "__main__":
    port = int(sys.argv[1])
    output_filename = sys.argv[2]

    S = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    S.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    S.bind(("0.0.0.0", port))
    OUTPUT_FILE = open(output_filename, "wb")

    receive_packets()

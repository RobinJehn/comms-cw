# Robin Jehn s2024553

import sys
import socket
import struct
import time
from utils import SequenceNumber, send_file, HEADER_FORMAT, log


class NoRetry:
    def __init__(self, host: str, port: int):
        """
        Params:
            host: The host to send the data to
            port: The port to send the data to
        """
        self.seq_num = SequenceNumber()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while True:
            try:
                self.sock.connect((host, port))
                break
            except socket.error:
                log("Connection failed, retrying...")
                time.sleep(1)

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
        self.sock.sendall(packet)
        self.seq_num.next()
        # We need to sleep a bit to avoid the receiver getting overwhelmed
        time.sleep(0.001)

        return True

    def __del__(self):
        """
        Destructor to ensure the socket is closed when the object is deleted
        """
        self.sock.close()


if __name__ == "__main__":
    remoteHost = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]

    sender = NoRetry(remoteHost, port)
    send_file(filename, sender)
    sender.sock.close()

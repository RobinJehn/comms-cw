# Utils file to be used by all senders and receivers
import os
import math

# Common variables
PACKET_SIZE = 1024
HEADER_SIZE = 3
LOGGING = False
HEADER_FORMAT = "!H?"

# Log function to easily turn on and off all logging for debugging
def log(msg: str):
    if LOGGING:
        print(msg)


# Class to keep track of the sequence number
class SequenceNumber:
    def __init__(self, max_seq_num: int | None = None):
        """
        Params:
        max_seq_num: The maximum sequence number to use. If None, we use 2^16 because we use a 2 byte sequence number
        """
        self.seq_num = 0
        self.max_seq_num = int(math.pow(2, 16)) if max_seq_num is None else max_seq_num

    def next(self) -> None:
        self.seq_num = (self.seq_num + 1) % self.max_seq_num

    def __call__(self) -> int:
        return self.seq_num


def send_file(filename: str, sender):
    """
    Params:
        filename: The name of the file to send
        sender: The sender object to use to send the file
    """
    file_size = os.path.getsize(filename)
    total_packets = math.ceil(file_size / PACKET_SIZE)

    with open(filename, "rb") as f:
        sent_packets = 0
        while True:
            # Get the data
            data = f.read(PACKET_SIZE)
            eof_flag = sent_packets + 1 == total_packets

            if eof_flag:
                log("Sending last packet")
                # If sending the last packet fails we don't want to retry
                sender.send(data, eof_flag)
            else:
                retry_count = 0
                max_retries = 100
                while not sender.send(data, eof_flag):
                    retry_count += 1
                    if retry_count >= max_retries:
                        log(f"Failed to send packet after {max_retries} retries")
                        return
            sent_packets += 1

            if eof_flag:
                break

# Utils file to be used by all senders and receivers
# Common variables
PACKET_SIZE = 1024
LOGGING = True


# Log function to easily turn on and off all logging for debugging
def log(msg: str):
    if LOGGING:
        print(msg)


# Class to keep track of the sequence number
class SequenceNumber:
    def __init__(self, max_seq_num: int | None = None):
        """
        Params:
        max_seq_num: The maximum sequence number to use. If None, the sequence number will be incremented indefinitely.
        """
        self.seq_num = 0
        self.max_seq_num = max_seq_num

    def next(self) -> None:
        if self.max_seq_num is None:
            self.seq_num += 1
        else:
            self.seq_num = (self.seq_num + 1) % self.max_seq_num

    def __call__(self, *args, **kwds) -> int:
        return self.seq_num

#!/bin/bash
# Bash script to run iperf TCP tests with varying window sizes

# List of window sizes to test (in KB)
window_sizes=(1 2 4 8 16 32)

# Test duration in seconds for each run
duration=30

# File to be transferred (adjust this to your actual file)
file_to_transfer="/home/user/testfile"

# Maximum Segment Size (MSS) set to 1024 bytes (1KB)
mss=1024

# Server address (assuming server is running on localhost)
server="localhost"

sudo tc qdisc del dev lo root
sudo tc qdisc add dev lo root netem loss 5% delay 25 rate 10mbit

# Loop through each window size and run iperf test
for ws in "${window_sizes[@]}"; do
    echo "Running iperf test with TCP window size: ${ws}KB"
    iperf -c "$server" -M "$mss" -w "${ws}KB" -F "$file_to_transfer" -t "$duration" > "iperf_ws_${ws}KB.txt"
    echo "Results for window size ${ws}KB saved to iperf_ws_${ws}KB.txt"
done

echo "All tests completed."

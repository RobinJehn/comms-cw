#!/bin/bash
# Start the iperf server in the background
echo "Starting iperf server..."
iperf -s -M 1024 > iperf_server.log 2>&1 &
server_pid=$!

# Allow the server time to initialize
sleep 2

# List of TCP window sizes to test (in KB)
window_sizes=(1 2 4 8 16 3)

# Test duration (in seconds) for each run
duration=30

# File to be transferred (adjust the path as necessary)
file_to_transfer="tett.jpg"

# Maximum Segment Size (MSS) in bytes (1KB)
mss=1024

# Loop through each window size and run iperf client test
for ws in "${window_sizes[@]}"; do
    echo "Running iperf test with TCP window size: ${ws}KB"
    iperf -c localhost -M "$mss" -w "${ws}KB" -F "$file_to_transfer" -t "$duration" > "iperf_ws_${ws}KB.txt"
    echo "Results for window size ${ws}KB saved to iperf_ws_${ws}KB.txt"
done

# Shut down the iperf server
echo "Stopping iperf server (PID: $server_pid)..."
kill $server_pid

echo "All tests completed."

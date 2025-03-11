#!/bin/bash

total_total_retransmissions=0
total_total_throughput=0

iterations=5

for i in $(seq 1 $iterations)
do
    echo "Iteration $i"
    rm -f abc.png
    
    # Run Receiver2.py in background
    python3 Receiver2.py 12345 abc.png &
    RECEIVER_PID=$!
    
    # Run Sender2.py and capture its output (run in the foreground)
    output=$(python3 Sender2.py localhost 12345 test.jpg 5)
    
    # Wait for the Receiver process to finish
    wait $RECEIVER_PID

    # Extract total_retransmissions and throughput from the output
    total_retransmissions=$(echo "$output" | awk '{print $1}')
    throughput=$(echo "$output" | awk '{print $2}')
    
    total_total_retransmissions=$(( total_total_retransmissions + total_retransmissions ))
    total_total_throughput=$(( total_total_throughput + throughput ))
    
    # Check for differences between the files
    if diff abc.png test.jpg > /dev/null; then
        echo "No differences found between abc.png and test.jpg"
    else
        echo "Differences found between abc.png and test.jpg"
    fi
done

echo "Average total retransmissions: $(( total_total_retransmissions / iterations ))"
echo "Average total throughput: $(( total_total_throughput / iterations ))"

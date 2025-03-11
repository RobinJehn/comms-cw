#!/bin/bash

# Define test values and number of iterations per test value
test_values=(5 10 15 20 25 30 40 50 75 100)
iterations=5

for value in "${test_values[@]}"; do
    echo "----------------------------"
    echo "Testing with parameter value: $value"
    
    total_total_retransmissions=0
    total_total_throughput=0
    
    for i in $(seq 1 $iterations); do
        echo "Iteration $i for value $value"
        rm -f abc.png
        
        # Run Receiver2.py in the background
        python3 Receiver2.py 12345 abc.png &
        RECEIVER_PID=$!
        
        # Run Sender2.py with the current test value and capture its output
        output=$(python3 Sender2.py localhost 12345 test.jpg $value)
        
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
    
    # Calculate and display averages for the current test value
    avg_retransmissions=$(( total_total_retransmissions / iterations ))
    avg_throughput=$(( total_total_throughput / iterations ))
    
    echo "For parameter value $value:"
    echo "  Average total retransmissions: $avg_retransmissions"
    echo "  Average total throughput: $avg_throughput"
done

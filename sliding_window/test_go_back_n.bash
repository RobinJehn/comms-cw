#!/bin/bash

# Define test values and number of iterations per test value
test_values=(5 25 100)
iterations=5

# Define window sizes as powers of 2 from 1 to 256
window_sizes=(1 2 4 8 16 32 64 128 256)

for value in "${test_values[@]}"; do
    echo "----------------------------"
    echo "Testing with parameter value: $value"
    
    # Set up the network conditions
    sudo tc qdisc del dev lo root
    sudo tc qdisc add dev lo root netem loss 5% delay $value rate 10mbit

    for window_size in "${window_sizes[@]}"; do
        echo ">> Testing with window size: $window_size"
        
        total_total_throughput=0
        
        for i in $(seq 1 $iterations); do
            echo "  Iteration $i for value $value with window size $window_size"
            rm -f abc.png
            
            # Run Receiver3.py in the background
            python3 Receiver3.py 12345 abc.png &
            receiver_pid=$!

            sleep 0.5

            # Run Sender3.py in the background and redirect its output to a temporary file
            python3 Sender3.py localhost 12345 test.jpg $((2 * value + 10)) $window_size > sender_output.txt &
            sender_pid=$!

            # Wait for both processes to finish
            wait $receiver_pid
            echo "Receiver finished"
            wait $sender_pid
            echo "Sender finished" 

            sleep 0.5
            
            # Read the sender output from the file
            output=$(cat sender_output.txt)
            rm sender_output.txt

            # Extract total_retransmissions and throughput from the output
            echo "$output"
            throughput=$(echo "$output" | tail -n 1 | awk '{print $1}')
            
            echo "    Throughput: $throughput"
            total_total_throughput=$(( total_total_throughput + throughput ))
            
            # Check for differences between the files
            if diff abc.png test.jpg > /dev/null; then
                echo "    No differences found between abc.png and test.jpg"
            else
                echo "    Differences found between abc.png and test.jpg"
                echo "$(diff abc.png test.jpg)"
                echo "$(ls -ahl abc.png)"
            fi
        done
        
        # Calculate and display averages for the current window size
        avg_throughput=$(( total_total_throughput / iterations ))
        
        echo "For parameter value $value and window size $window_size:"
        echo "  Average total throughput: $avg_throughput"
        echo ""
    done
done

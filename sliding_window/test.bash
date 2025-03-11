#!/bin/bash

for i in {1..5}
do
    echo "Iteration $i"
    
    # Run Receiver2.py and Sender2.py in parallel
    python3 Receiver2.py 12345 abc.png &
    RECEIVER_PID=$!
    
    python3 Sender2.py localhost 12345 test.jpg 5 &
    SENDER_PID=$!
    
    # Wait for both processes to finish
    wait $RECEIVER_PID
    wait $SENDER_PID
    
    # Check for differences between the files
    if diff abc.png test.jpg > /dev/null; then
        echo "No differences found between abc.png and test.jpg"
    else
        echo "Differences found between abc.png and test.jpg"
    fi
done
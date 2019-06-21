#!/bin/bash
nohup python ./scripts/run_server.py &
echo "starting run_server.py loading sophia personality pausing for 25 seconds"
echo "....."
echo "loading Sophia chat client (35 second delay)"
echo "....."
sleep 35
echo "....."
echo "loading..."
sleep 2
python ./scripts/client.py

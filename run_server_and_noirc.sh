#!/bin/bash
sudo nohup python ./scripts/run_server.py &
echo "starting run_server.py loading sophia personality pausing for 2 seconds"
sleep 2
echo "....."
echo "loading Sophia chat client"
echo "....."
sleep 2
echo "....."
echo "loading..."
sleep 2
sudo python ./scripts/client.py

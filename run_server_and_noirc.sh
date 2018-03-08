#!/bin/bash
sudo nohup python ./scripts/run_server.py &
echo "starting run_server.py loading sophia personality pausing for 10 seconds"
sleep 10
echo "....."
echo "loading Sophia chat client"
echo "....."
sleep 10
echo "....."
echo "loading..."
sleep 2
sudo python ./scripts/client.py

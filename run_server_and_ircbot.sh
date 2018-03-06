#!/bin/bash
sudo nohup python ./scripts/run_server.py &
echo "starting run_server.py loading sophia personality pausing for 30 seconds"
sleep 30
echo "....."
echo "loading Sophia irc bot"
echo "....."
echo "check server config in Sophia.py for channel botname and server pause for 20 seconds"
sleep 20
echo "....."
echo "loading..."
sleep 2
sudo python ./scripts/Sophia.py

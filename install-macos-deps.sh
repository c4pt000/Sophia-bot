#!/bin/bash
echo 'run as root, script will pause for 5 seconds'
sleep 5
curl https://bootstrap.pypa.io/ez_setup.py | python
easy_install pip
pip install --ignore-installed six
pip install --ignore-installed numpy
pip install flask pyyaml pandas flask num2words twisted requests

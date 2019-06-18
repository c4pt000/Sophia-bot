#!/bin/bash
echo 'run as root'
easy_install pip
pip install --ignore-installed six
pip install --ignore-installed numpy
pip install flask pyyaml pandas flask num2words twisted requests

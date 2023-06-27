#!/bin/bash

7z x -y vpn/data/central.zip -o/etc/tinc/VNOICup
chmod +x /etc/tinc/VNOICup/tinc-up
chmod +x /etc/tinc/VNOICup/tinc-down

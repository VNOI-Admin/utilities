#!/bin/bash

wget -O vpn-cfg.zip "$SERVER_ADDRESS/configs/$USERNAME.zip"
7z x -y -p$PASSWORD vpn-cfg.zip -o/etc/tinc/VNOICup
chmod +x /etc/tinc/VNOICup/tinc-up
chmod +x /etc/tinc/VNOICup/tinc-down
rm vpn-cfg.zip

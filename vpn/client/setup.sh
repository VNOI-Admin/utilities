#!/bin/bash

SERVER_ADDRESS="100.0.0.1"

curl -s "$SERVER_ADDRESS/configs/$USER.zip" > unzip - -d /etc/tinc/VNOICup

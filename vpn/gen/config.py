from os import path
from ipaddress import ip_address

USER_BASE_SUBNET = ip_address("10.0.0.0")
SERVICE_BASE_SUBNET = ip_address("10.1.0.0")

DATA_PATH = path.join("vpn", "data")

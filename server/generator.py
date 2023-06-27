import string
from os import path
from csv import DictReader, DictWriter
from io import BytesIO, StringIO
from ipaddress import ip_address
from zipfile import ZipFile
import secrets
from Crypto.PublicKey import RSA

IP_PREFIX_WIDTH = 32
VPN_NAME = "VNOICup"
BASE_SUBNET_ADDRESS = ip_address("10.0.0.1")


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate a random key pair"""
    private_key = RSA.generate(2048)
    public_key = private_key.public_key()
    return private_key.export_key(), public_key.export_key()


def generate_host_config(subnet_address: str, public_key: bytes) -> bytes:
    host_config = StringIO()
    print(f"Subnet = {subnet_address}/{IP_PREFIX_WIDTH}", file=host_config)
    print("", file=host_config)
    print(public_key, file=host_config)
    return host_config.getvalue()


def generate_tinc_config(username: str) -> bytes:
    tinc_conf = StringIO()
    print(f"Name = {username}", file=tinc_conf)
    print("AddressFamily = ipv4", file=tinc_conf)
    print(f"ConnectTo = {VPN_NAME}", file=tinc_conf)
    return tinc_conf.getvalue()


def generate_tinc_script(subnet_address: str) -> bytes:
    tinc_up = StringIO()
    print("#!/bin/bash", file=tinc_up)
    print("ip link set $INTERFACE up", file=tinc_up)
    print(
        f"ip addr add {subnet_address}/{IP_PREFIX_WIDTH} dev $INTERFACE", file=tinc_up)
    print("ip route add 10.0.0.0/16 dev $INTERFACE", file=tinc_up)
    return tinc_up.getvalue()


def generate_config(username: str, subnet_address: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as zip:
        private_key, public_key = generate_keypair()
        zip.writestr("rsa_key.priv", private_key)
        zip.writestr("rsa_key.pub", public_key)

        # TODO: Write central host file
        zip.writestr(f"hosts/{username}",
                     generate_host_config(subnet_address, public_key))

        zip.writestr("tinc.conf", generate_tinc_config(username))

        zip.writestr("tinc-up", generate_tinc_script(subnet_address))
        # TODO: host-up
    return buffer.getvalue()


def get_subnet_address(subnet_address: str, idx: int) -> str:
    expected_address = ip_address(BASE_SUBNET_ADDRESS + idx).exploded
    if subnet_address != "" and subnet_address != expected_address:
        print(f"subnet_address and expected_address doesn't match")
        return subnet_address
    return expected_address


def get_password(password: str) -> str:
    if password == "":
        return "".join([secrets.choice(string.ascii_letters) for _ in range(8)])
    return password


def create_all_users():
    new_user_list_f = StringIO()
    new_user_list = DictWriter(
        new_user_list_f, ["Username", "SubnetAddress", "Password"])
    new_user_list.writeheader()

    with open(path.join("data", "userlist.csv"), "r") as user_list_f:
        user_list = DictReader(user_list_f)
        for idx, user in enumerate(user_list):
            username = user["Username"]
            user["SubnetAddress"] = subnet_address = get_subnet_address(
                user["SubnetAddress"], idx)
            user["Password"] = password = get_password(user["Password"])

            print(f"Config for {username}")
            config_zip = generate_config(username, subnet_address)

            with open(path.join("data", "static", f"{username}.{password}.zip"), "wb") as zip_f:
                zip_f.write(config_zip)
            new_user_list.writerow(user)

    with open(path.join("data", "userlist1.csv"), "w") as user_list_new_f:
        content = new_user_list_f.getvalue()
        content = "\n".join([line for line in content.splitlines() if line])
        print(content, file=user_list_new_f)


if __name__ == "__main__":
    create_all_users()

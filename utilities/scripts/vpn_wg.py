from io import BytesIO, StringIO
from Cryptodome.PublicKey import RSA
from pyzipper import AESZipFile, WZ_AES
from os import path
from csv import DictWriter, DictReader
from ipaddress import ip_address
import subprocess

from pony.orm import db_session

from utilities.models import User

BASE_SUBNET = ip_address("10.0.0.0")
USER_BASE_SUBNET = ip_address("10.0.0.0")
SERVICE_BASE_SUBNET = ip_address("10.1.0.0")
CENTRAL_BASE_SUBNET = ip_address("10.1.0.1")

listen_port = "51820"

endpoint = f"vpn.vnoi.info:{listen_port}"

preshared_key = True

dns = "1.1.1.1"

class VPNNode:
    def __init__(self, name: str, password: str, subnet_ip: str, public_ip=None):
        self.name = name
        self.password = password
        self.subnet_ip = subnet_ip
        if public_ip is not None and public_ip != "":
            self.public_ip = public_ip
        self.generate_keypair()
        self.config = self.generate_config()

    def generate_keypair(self):
        private = subprocess.check_output(["wg", "genkey"]).decode().strip()
        public = subprocess.check_output(["wg", "pubkey"], input=private.encode()).decode().strip()
        self.private_key = private
        self.public_key = public

    def generate_server_config(self):
        config = f"[Interface]\n"
        config += f"Address = {self.subnet_ip}/32\n"
        config += f"ListenPort = {listen_port}\n"
        config += f"PrivateKey = {self.private_key}\n"
        config += f"PostUp = iptables -w -t nat -A POSTROUTING -o eth0 -j MASQUERADE; " \
                "ip6tables -w -t nat -A POSTROUTING -o eth0 -j MASQUERADE\n"
        config += f"PostDown = iptables -w -t nat -D POSTROUTING -o eth0 -j MASQUERADE; " \
                "ip6tables -w -t nat -D POSTROUTING -o eth0 -j MASQUERADE\n"
        config += "\n"
        return config

    def generate_config(self):
        if self.subnet_ip == CENTRAL_BASE_SUBNET.exploded:
            return self.generate_server_config()
        config = f"[Interface]\n"
        config += f"PrivateKey = {self.private_key}\n"
        config += f"Address = {self.subnet_ip}/32\n"
        config += f"ListenPort = {listen_port}\n"
        # config += f"DNS = {dns}\n"
        config += "\n"
        return config

    def add_peer(self, node: "VPNNode"):
        peer_config = f"# {node.name}\n"
        peer_config += f"[Peer]\n"
        peer_config += f"PublicKey = {node.public_key}\n"
        if node.subnet_ip == CENTRAL_BASE_SUBNET.exploded:
            peer_config += f"AllowedIPs = 10.0.0.0/8\n"  # This will be dealt with by custom iptables rules
        if self.subnet_ip == CENTRAL_BASE_SUBNET.exploded:
            peer_config += f"AllowedIPs = {node.subnet_ip}/32\n"
        else:
            peer_config += f"Endpoint = {endpoint}\n"
        peer_config += f"PersistentKeepalive = 25\n"
        peer_config += "\n"
        self.config += peer_config

@db_session
def create_users() -> list[VPNNode]:
    user_nodes = []

    with open(path.join("data", "user.csv"), "r") as node_list_f:
        for node in DictReader(node_list_f):
            name, password = node["Name"], node["Password"]
            subnet_ip = node["SubnetIP"]

            user_nodes.append(VPNNode(name, password, subnet_ip))

            if User.select(lambda u: u.username == name).count() == 0:
                User(username=name, password=password, ip_address=subnet_ip)
            else:
                user = User.select(lambda u: u.username == name).first()
                user.password = password
                user.ip_address = subnet_ip

    return user_nodes


def create_services() -> list[VPNNode]:
    service_nodes = []
    with open(path.join("data", "service.csv"), "r") as node_list_f:
        for node in DictReader(node_list_f):
            name, password = node["Name"], node["Password"]
            public_ip, subnet_ip = node["PublicIP"], node["SubnetIP"]


            service_nodes.append(VPNNode(name, password, subnet_ip, public_ip))
    return service_nodes


def create_all():
    user_nodes = create_users()
    service_nodes = create_services()
    central = service_nodes[0]
    service_nodes = service_nodes[1:]

    for service in service_nodes:
        central.add_peer(service)
        service.add_peer(central)

    for user in user_nodes:
        user.add_peer(central)
        central.add_peer(user)

    for node in user_nodes + service_nodes + [central]:
        with open(path.join("data", "configs", f"{node.name}.conf"), "w") as f:
            f.write(node.config)
        print("Wrote node", node.name)


if __name__ == '__main__':
    create_all()

from io import BytesIO, StringIO
from Crypto.PublicKey import RSA
from pyzipper import AESZipFile, WZ_AES
from os import path
from csv import DictWriter, DictReader
from ipaddress import ip_address

RSA_LENGTH = 2048
IP_PREFIX_WIDTH = 8
BASE_SUBNET = ip_address("10.0.0.0")
USER_BASE_SUBNET = ip_address("10.0.0.0")
SERVICE_BASE_SUBNET = ip_address("10.1.0.0")


class VPNNode:
    def __init__(self, name: str, password: str, subnet_ip: str, public_ip: str | None = None):
        self.name = name
        self.password = password
        self.subnet_ip = subnet_ip
        if public_ip is not None and public_ip != "":
            self.public_ip = public_ip
        self.__generate_keypair()
        self.__generate_hosts()
        self.__generate_tinc_conf()
        self.__generate_scripts()

    def __generate_keypair(self):
        private = RSA.generate(RSA_LENGTH)
        public = private.public_key()
        self.private_key = private.export_key().decode()
        self.public_key = public.export_key().decode()

    def __generate_hosts(self):
        try:
            hosts_file = f"Address = {self.public_ip}\n"
        except AttributeError:
            hosts_file = ""
        hosts_file += f"Subnet = {self.subnet_ip}/{IP_PREFIX_WIDTH}\n\n"
        hosts_file += self.public_key + "\n"
        self.hosts = self.name, hosts_file
        self.endpoints_hosts = [self.hosts]

    def __generate_tinc_conf(self):
        self.tinc_conf = f"Name = {self.name}\n"
        self.tinc_conf += "AddressFamily = ipv4\n"
        # Stop communication between contestants
        self.tinc_conf += "DirectOnly = yes\n"

    def __generate_scripts(self):
        self.tinc_up = "#!/bin/bash\n"
        self.tinc_up += "ip link set $INTERFACE up\n"
        self.tinc_up += f"ip addr add {self.subnet_ip}/{IP_PREFIX_WIDTH} dev $INTERFACE\n"
        self.tinc_up += f"ip route add {BASE_SUBNET.exploded}/{IP_PREFIX_WIDTH} dev $INTERFACE\n"

        self.tinc_down = "#!/bin/bash\n"
        self.tinc_down += f"ip route del {BASE_SUBNET.exploded}/{IP_PREFIX_WIDTH} dev $INTERFACE\n"
        self.tinc_down += f"ip addr del {self.subnet_ip}/{IP_PREFIX_WIDTH} dev $INTERFACE\n"
        self.tinc_down += "ip link set $INTERFACE down\n"

    def connect_to(self, endpoint: "VPNNode"):
        self.endpoints_hosts.append(endpoint.hosts)
        endpoint.endpoints_hosts.append(self.hosts)
        self.tinc_conf += f"ConnectTo = {endpoint.subnet_ip}\n"

    def export_zip(self) -> bytes:
        buffer = BytesIO()
        with AESZipFile(buffer, "w") as zip_f:
            if self.password != "":
                zip_f.setpassword(self.password.encode())
                zip_f.setencryption(WZ_AES, nbits=256)

            zip_f.writestr("rsa_key.pub", self.public_key)
            zip_f.writestr("rsa_key.priv", self.private_key)

            for host_name, hosts in self.endpoints_hosts:
                zip_f.writestr(f"hosts/{host_name}", hosts)

            zip_f.writestr("tinc.conf", self.tinc_conf)

            zip_f.writestr("tinc-up", self.tinc_up)
            zip_f.writestr("tinc-down", self.tinc_up)

        return buffer.getvalue()


def create_users() -> list[VPNNode]:
    user_nodes = []
    with open(path.join("vpn", "data", "user.csv"), "r") as node_list_f:
        for node in DictReader(node_list_f):
            name, password = node["Name"], node["Password"]
            subnet_ip = node["SubnetIP"]

            expected_subnet_ip = (
                USER_BASE_SUBNET + len(user_nodes) + 1).exploded
            assert expected_subnet_ip == subnet_ip or subnet_ip == "" or subnet_ip is None

            user_nodes.append(VPNNode(name, password, expected_subnet_ip))
    return user_nodes


def write_users(user_nodes: list[VPNNode]):
    buffer = StringIO()
    writer = DictWriter(buffer, ["Name", "Password", "SubnetIP"])
    writer.writeheader()

    for node in user_nodes:
        writer.writerow({
            "Name": node.name,
            "Password": node.password,
            "SubnetIP": node.subnet_ip})
        with open(path.join("vpn", "data", "user_configs", f"{node.name}.zip"), "wb") as f:
            f.write(node.export_zip())

    file_content = buffer.getvalue()
    file_content = "\n".join(
        [line for line in file_content.splitlines() if line])

    with open(path.join("vpn", "data", "user1.csv"), "w") as node_list_f:
        node_list_f.write(file_content)


def create_services() -> list[VPNNode]:
    service_nodes = []
    with open(path.join("vpn", "data", "service.csv"), "r") as node_list_f:
        for node in DictReader(node_list_f):
            name, password = node["Name"], node["Password"]
            public_ip, subnet_ip = node["PublicIP"], node["SubnetIP"]

            expected_subnet_ip = (SERVICE_BASE_SUBNET +
                                  len(service_nodes) + 1).exploded
            assert expected_subnet_ip == subnet_ip or subnet_ip == "" or subnet_ip is None

            service_nodes.append(
                VPNNode(name, password, expected_subnet_ip, public_ip))
    return service_nodes


def write_services(service_nodes: list[VPNNode]):
    buffer = StringIO()
    writer = DictWriter(buffer, ["Name", "Password", "PublicIP", "SubnetIP"])
    writer.writeheader()
    for node in service_nodes:
        writer.writerow({
            "Name": node.name,
            "Password": node.password,
            "PublicIP": node.public_ip,
            "SubnetIP": node.subnet_ip})
        with open(path.join("vpn", "data", "service_configs", f"{node.name}.zip"), "wb") as f:
            f.write(node.export_zip())

    file_content = buffer.getvalue()
    file_content = "\n".join(
        [line for line in file_content.splitlines() if line])

    with open(path.join("vpn", "data", "service1.csv"), "w") as node_list_f:
        node_list_f.write(file_content)


def create_all():
    user_nodes = create_users()
    service_nodes = create_services()

    for service in service_nodes:
        for user in user_nodes:
            user.connect_to(service)

    for service in service_nodes[1:]:
        service.connect_to(service_nodes[0])

    write_users(user_nodes)
    write_services(service_nodes)


if __name__ == '__main__':
    create_all()

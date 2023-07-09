from io import BytesIO
from ipaddress import ip_address
from pyzipper import AESZipFile, WZ_AES
from Crypto.PublicKey import RSA

RSA_LENGTH = 2048
BASE_SUBNET = ip_address("10.0.0.0")
GLOBAL_PREFIX_WIDTH = 8


class VPNNode:
    def __generate_keypair(self) -> 'tuple[bytes, bytes]':
        private_key = self.key.export_key()
        public_key = self.key.public_key().export_key()
        return private_key.decode(), public_key.decode()

    def __generate_hosts(self) -> 'tuple[str, str]':
        hosts_file = ""
        if self.public_ip != "":
            hosts_file = f"Address = {self.public_ip}\n"
        hosts_file += f"Subnet = {self.subnet_ip}/32\n\n"
        hosts_file += self.public_key + "\n"
        hosts = self.name, hosts_file
        return hosts

    def __generate_tinc_conf(self) -> str:
        tinc_conf = f"Name = {self.name}\n"
        tinc_conf += "AddressFamily = ipv4\n"
        # Stop communication if hosts file not present
        tinc_conf += "StrictSubnets = yes\n"
        return tinc_conf

    def __generate_scripts(self) -> 'tuple[str, str]':
        tinc_up = "#!/bin/bash\n"
        tinc_up += "ip link set $INTERFACE up\n"
        tinc_up += f"ip addr add {self.subnet_ip}/32 dev $INTERFACE\n"
        tinc_up += f"ip route add {BASE_SUBNET.exploded}/{GLOBAL_PREFIX_WIDTH} dev $INTERFACE\n"

        tinc_down = "#!/bin/bash\n"
        tinc_down += f"ip route del {BASE_SUBNET.exploded}/{GLOBAL_PREFIX_WIDTH} dev $INTERFACE\n"
        tinc_down += f"ip addr del {self.subnet_ip}/32 dev $INTERFACE\n"
        tinc_down += "ip link set $INTERFACE down\n"
        return tinc_up, tinc_down

    def connect_to(self, endpoint: 'VPNNode'):
        self.endpoints_hosts.append(endpoint.hosts)
        endpoint.endpoints_hosts.append(self.hosts)
        self.tinc_conf += f"ConnectTo = {endpoint.name}\n"

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
            zip_f.writestr("tinc-down", self.tinc_down)

        return buffer.getvalue()

    def __init_node(self, name: str, password: str, subnet_ip: str, public_ip: str) -> 'VPNNode':
        self.name = name
        self.password = password
        self.subnet_ip = subnet_ip
        if public_ip is not None:
            self.public_ip = public_ip
        else:
            self.public_ip = ""

        self.private_key, self.public_key = self.__generate_keypair()
        self.hosts = self.__generate_hosts()
        self.endpoints_hosts = [self.hosts]

        self.tinc_conf = self.__generate_tinc_conf()
        self.tinc_up, self.tinc_down = self.__generate_scripts()

    @staticmethod
    def from_meta(name: str, password: str,
                  subnet_ip: str, public_ip: str) -> 'VPNNode':
        self = VPNNode()
        self.key = RSA.generate(RSA_LENGTH)
        self.__init_node(name, password, subnet_ip, public_ip)
        return self

    @staticmethod
    def from_cached(f: str, name: str, password: str,
                    subnet_ip: str, public_ip: str) -> 'VPNNode':
        self = VPNNode()
        with AESZipFile(f, "r") as buffer:
            self.key = RSA.import_key(buffer.read(
                "rsa_key.priv", password.encode()))
        self.__init_node(name, password, subnet_ip, public_ip)
        return self

from io import BytesIO
from Crypto.PublicKey import RSA
from pyzipper import AESZipFile, WZ_AES
IP_PREFIX_WIDTH = 32
 
class VPNNode:
    def __init__(self, name: str, subnet_ip: str, public_ip: str | None = None):
        self.name = name
        self.subnet_ip = subnet_ip
        if public_ip is not None:
            self.public_ip = public_ip
        self.__generate_keypair()
        self.__generate_hosts()
        self.__generate_tinc_conf()
        self.__generate_scripts()

    def __generate_keypair(self):
        private = RSA.generate(2048)
        public = private.public_key()
        self.private_key = private.export_key().decode()
        self.public_key = public.export_key().decode()
    
    def __generate_hosts(self):
        hosts_file = ""
        try:
            hosts_file += f"Address = {self.public_ip}\n"
        except AttributeError:
            pass
        hosts_file += f"Subnet = {self.subnet_ip}/{IP_PREFIX_WIDTH}\n\n"
        hosts_file += self.public_key + "\n"
        self.hosts = self.name, self.hosts
        self.endpoints_hosts = [self.hosts]
    
    def __generate_tinc_conf(self):
        self.tinc_conf = f"Name = {self.name}\n"
        self.tinc_conf += "AddressFamily = ipv4\n"
    
    def __generate_scripts(self):
        self.tinc_up = "#!/bin/bash\n"
        self.tinc_up += "ip link set $INTERFACE up\n"
        self.tinc_up += f"ip addr add {self.subnet_ip}/{IP_PREFIX_WIDTH} dev $INTERFACE\n"
        self.tinc_up += f"ip route add 10.0.0.0/{IP_PREFIX_WIDTH} dev $INTERFACE"

        self.tinc_down = "#!/bin/bash\n"
        self.tinc_down += f"ip route del 10.0.0.0/{IP_PREFIX_WIDTH} dev $INTERFACE\n"
        self.tinc_down += f"ip addr del {self.subnet_ip}/{IP_PREFIX_WIDTH} dev $INTERFACE\n"
        self.tinc_down += "ip link set $INTERFACE down\n"
    
    def connect_to(self, endpoint: "VPNNode"):
        self.endpoints_hosts.append(endpoint.hosts)
        self.tinc_conf += f"ConnectTo = {endpoint.subnet_ip}\n"
    
    def export_zip(self, password: str):
        buffer = BytesIO()
        with AESZipFile(buffer, "w") as zip_f:
            if password != "":
                zip_f.setpassword(password.encode())
                zip_f.setencryption(WZ_AES, nbits=256)
            
            zip_f.writestr("rsa_key.pub", self.public_key)
            zip_f.writestr("rsa_key.priv", self.private_key)

def connect_nodes(a: VPNNode, b: VPNNode):
    a.connect_to(b)
    b.connect_to(a)

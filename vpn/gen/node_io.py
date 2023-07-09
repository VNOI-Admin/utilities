from io import BytesIO
from os import path
from node import VPNNode
from pyzipper import AESZipFile

def zip_path(name: str) -> str:
    return str(path.join("vpn", "data", "configs", f"{name}.zip"))

def zipfile_diff(a: bytes, b: bytes, password: str) -> bool:
    with AESZipFile(BytesIO(a), "r") as lhs, AESZipFile(BytesIO(b), "r") as rhs:
        lhs.setpassword(password.encode())
        rhs.setpassword(password.encode())

        namelist = lhs.namelist()
        if namelist != rhs.namelist():
            return True
        for filename in namelist:
            if lhs.read(filename) != rhs.read(filename):
                return True
    return False

def write_node(node: VPNNode):
    new_file = node.export_zip()
    expected_path = zip_path(node.name)

    if path.exists(expected_path):
        with open(expected_path, "rb") as f:
            old_file = f.read()
        if zipfile_diff(old_file, new_file, node.password):
            print(f"Modified: {node.name}")
            with open(zip_path(node.name + "_old"), "wb") as old_f:
                old_f.write(old_file)
    else:
        print(f"Created: {node.name}")

    with open(expected_path, "wb") as f:
        f.write(new_file)


def read_node(name: str, password: str,
              subnet_ip: str, public_ip: str | None = None) -> VPNNode:
    expected_path = zip_path(name)
    if path.exists(expected_path):
        return VPNNode.from_cached(expected_path, name, password, subnet_ip, public_ip)
    else:
        return VPNNode.from_meta(name, password, subnet_ip, public_ip)

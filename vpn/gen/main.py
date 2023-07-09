from io import StringIO
from os import path
from csv import DictWriter, DictReader
from ipaddress import ip_address
from node import VPNNode
import node_io

USER_BASE_SUBNET = ip_address("10.0.0.0")
SERVICE_BASE_SUBNET = ip_address("10.1.0.0")


def read_csv_buffer(buffer: StringIO) -> str:
    file_content = buffer.getvalue()
    file_content = "\n".join(
        [line for line in file_content.splitlines() if line])
    return file_content


def create_nodes(csv_path: str, base_subnet: ip_address) -> list[VPNNode]:
    nodes = []
    with open(path.join(csv_path), "r") as node_list_f:
        for node in DictReader(node_list_f):
            name, password = node["Name"], node["Password"]
            public_ip, subnet_ip = node["PublicIP"], node["SubnetIP"]

            expected_subnet_ip = (
                base_subnet + len(nodes) + 1).exploded
            assert expected_subnet_ip == subnet_ip or subnet_ip == "" or subnet_ip is None
            nodes.append(node_io.read_node(
                name, password, expected_subnet_ip, public_ip))

    return nodes


def write_nodes(csv_path: str, nodes: list[VPNNode]):
    buffer = StringIO()
    writer = DictWriter(buffer, ["Name", "Password", "PublicIP", "SubnetIP"])
    writer.writeheader()

    for node in nodes:
        writer.writerow({
            "Name": node.name,
            "Password": node.password,
            "PublicIP": node.public_ip,
            "SubnetIP": node.subnet_ip})
        node_io.write_node(node)

    with open(csv_path, "w") as node_list_f:
        node_list_f.write(read_csv_buffer(buffer))


def create_all():
    user_nodes = create_nodes(path.join("vpn", "data", "user.csv"), USER_BASE_SUBNET)
    service_nodes = create_nodes(path.join("vpn", "data", "service.csv"), SERVICE_BASE_SUBNET)

    for service in service_nodes:
        for user in user_nodes:
            user.connect_to(service)

    for service in service_nodes[1:]:
        service.connect_to(service_nodes[0])

    write_nodes(path.join("vpn", "data", "user1.csv"), user_nodes)
    write_nodes(path.join("vpn", "data", "service1.csv"), service_nodes)


if __name__ == '__main__':
    create_all()

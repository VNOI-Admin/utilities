from io import StringIO
from os import path
from csv import DictWriter, DictReader
from ipaddress import ip_address
from node import VPNNode
import version
import config
from sys import argv

old_version = version.OldVersion(argv[1])
new_version = version.NewVersion(old_version, argv[2])

def read_csv_buffer(buffer: StringIO) -> str:
    file_content = buffer.getvalue()
    file_content = "\n".join(
        [line for line in file_content.splitlines() if line])
    return file_content


def create_nodes(csv_path: str, base_subnet: ip_address) -> 'list[VPNNode]':
    nodes = []
    with open(path.join(csv_path), "r") as node_list_f:
        for node in DictReader(node_list_f):
            name, password = node["Name"], node["Password"]
            public_ip, subnet_ip = node["PublicIP"], node["SubnetIP"]

            expected_subnet_ip = (
                base_subnet + len(nodes) + 1).exploded
            assert expected_subnet_ip == subnet_ip or subnet_ip == "" or subnet_ip is None
            nodes.append(old_version.read_node(
                name, password, expected_subnet_ip, public_ip))

    return nodes


def write_nodes(csv_path: str, nodes: 'list[VPNNode]'):
    buffer = StringIO()
    writer = DictWriter(buffer, ["Name", "Password", "PublicIP", "SubnetIP"])
    writer.writeheader()

    for node in nodes:
        writer.writerow({
            "Name": node.name,
            "Password": node.password,
            "PublicIP": node.public_ip,
            "SubnetIP": node.subnet_ip})
        new_version.write_node(node)

    with open(csv_path, "w") as node_list_f:
        node_list_f.write(read_csv_buffer(buffer))


def create_all():
    user_nodes = create_nodes(
        path.join(config.DATA_PATH, "user.csv"), config.USER_BASE_SUBNET)
    service_nodes = create_nodes(
        path.join(config.DATA_PATH, "service.csv"), config.SERVICE_BASE_SUBNET)

    for service in service_nodes:
        for user in user_nodes:
            user.connect_to(service)

    for service in service_nodes[1:]:
        service.connect_to(service_nodes[0])

    write_nodes(new_version.csv_path("user"), user_nodes)
    write_nodes(new_version.csv_path("service"), service_nodes)


if __name__ == '__main__':
    create_all()

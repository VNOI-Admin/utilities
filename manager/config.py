import json
from collections import namedtuple


class ConfigError(Exception):
    pass


class Address(namedtuple('Address', ['host', 'port'])):
    def __repr__(self):
        return "%s:%d" % (self.host, self.port)


class ServiceCoord(namedtuple('ServiceCoord', ['name', 'shard'])):
    def __repr__(self) -> str:
        return "%s:%d" % (self.name, self.shard)


def get_service_address(service_coord: ServiceCoord):
    return config['services'][service_coord.name][int(service_coord.shard)]


config = json.load(open('config.json'))

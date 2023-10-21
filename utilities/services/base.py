import signal
import socket

import gevent
from gevent.server import StreamServer

from .rpc import rpc_method, RPCServiceServer, RPCServiceClient
from ..config import get_service_address, ConfigError, ServiceCoord


class Address:
    def __init__(self, host, port):
        self.host = host
        self.port = port


class Service:
    def __init__(self, shard=0):
        # gevent.signal_handler(signal.SIGTERM, self.exit)
        gevent.signal_handler(signal.SIGINT, self.exit)

        self.name = self.__class__.__name__

        self.remote_services = {}

        try:
            address = get_service_address(ServiceCoord(self.name, shard))
        except KeyError:
            raise ConfigError('Address for service %s not found' % self.name)

        self.rpc_server = StreamServer(address, self._connection_handler)

    def _connection_handler(self, sock, addr):
        address = Address(addr[0], addr[1])
        remote_service = RPCServiceServer(self, address)
        remote_service.handle(sock)
        print("Client connected: %s:%s" % (addr[0], addr[1]))

    def connect_to(self, coord, on_connect=None, on_disconnect=None):
        if coord not in self.remote_services:
            try:
                service = RPCServiceClient(coord, auto_retry=0.5)
            except KeyError:
                raise ConfigError("Missing address and port for %s" % (coord,))
            service.connect()
            self.remote_services[coord] = service
        else:
            service = self.remote_services[coord]

        if on_connect is not None:
            service.add_on_connect_handler(on_connect)

        if on_disconnect is not None:
            service.add_on_disconnect_handler(on_disconnect)

        return service

    def exit(self):
        self.rpc_server.stop()

    def run(self):
        try:
            self.rpc_server.start()
        except socket.gaierror as error:
            print("Error starting service %s: %s" % (self.name, error))
            return False
        except OSError as error:
            print("Error starting service %s: %s" % (self.name, error))
            return False

        print("Service %s started" % self.name)

        self.rpc_server.serve_forever()

        self._disconnect_all()
        return True

    def _disconnect_all(self):
        for service in self.remote_services.values():
            if service.connected:
                service.disconnect()

    @rpc_method
    def ping(self, string="ping"):
        return string

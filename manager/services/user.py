from pony.orm import db_session

from models import User, Printing
from config import Address, ServiceCoord
from .base import Service
from .rpc import RPCServiceServer, rpc_method


class UserRPCServiceServer(RPCServiceServer):
    def handle(self, sock, user):
        self.user = user
        return super().handle(sock)

    def process_data(self, data):
        data = super().process_data(data)
        data['__params']['user'] = self.user  # Add user to params
        return data


class UserHandlerService(Service):
    def __init__(self):
        super().__init__()

        self.user_service = self.connect_to(ServiceCoord("UserService", 0))

    @db_session
    def _connection_handler(self, sock, addr):
        user = User.select(lambda u: u.ip_address == addr[0])
        if len(user) != 1:
            raise Exception("User not found")
        user = user[0]
        user.is_online = True

        address = Address(addr[0], addr[1])
        remote_service = UserRPCServiceServer(self, address)
        remote_service.handle(sock, user)

    @rpc_method
    def print(self, source: str, user: User):
        self.register_print_job(user, source)
        # TODO: Call print method on printer service
        return True

    @db_session
    def register_print(self, caller: User, source: str):
        Printing(caller=caller, source=source)


class UserService(Service):
    def __init__(self):
        super().__init__()

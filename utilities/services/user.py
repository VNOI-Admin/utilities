import os

from flask import Flask, send_file
from flask_restful import Api, Resource, reqparse
from pony.orm import db_session

from gevent.pywsgi import WSGIServer

from utilities.models import User, Printing
from utilities.config import config, Address, ServiceCoord
from .base import Service
from .rpc import RPCServiceServer, rpc_method

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
api = Api(app)


@app.route('/')
def default():
    return 'Hello, World!'


@api.resource('/login')
class UserLogin(Resource):
    def __init__(self):
        super().__init__()
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('username', location='form')
        self.parser.add_argument('password', location='form')

    @db_session
    def post(self):
        # Get username and password from request
        args = self.parser.parse_args()
        username = args['username'] or ""
        password = args['password'] or ""
        user = User.get(username=username)

        if user is None:
            return {'error': 'User not found'}, 404
        elif not user.verify_password(password):
            return {'error': 'Incorrect password'}, 401
        elif not os.path.exists(os.path.join('data', 'configs', f'{username}.zip')):
            return {'error': 'User configuration not found'}, 404

        # TODO: Return VPN configurations
        return send_file(os.path.join('..', '..', 'data', 'configs', f'{username}.zip'))


class UserRPCServiceServer(RPCServiceServer):
    def handle(self, sock, user):
        self.user = user
        return super().handle(sock)

    def process_data(self, data):
        data = super().process_data(data)
        data['__params']['user'] = self.user  # Add user to params
        return data


class UserService(Service):
    def __init__(self):
        super().__init__(shard=0)

        self.printing_services = self.connect_to(ServiceCoord('PrintingService', 0))
        self._api = WSGIServer((config['api'][0], config['api'][1]), app)

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

    def run(self):
        self._api.start()
        return super().run()

    def exit(self):
        self._api.stop()
        super().exit()

    @db_session
    def register_print_job(self, caller: User, source: str):
        Printing(caller=caller, source=source)

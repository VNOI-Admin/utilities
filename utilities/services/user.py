import os
import json

from ping3 import ping
from flask import Flask, send_file
from flask_restful import Api, Resource, reqparse
from pony.orm import db_session

import gevent
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
    def __init__(self, remote_address):
        super().__init__(remote_address)

        self._ping = None

    @db_session
    def ping(self):
        while True:
            ping_ = round(ping(self.remote_address.host) * 1000, 3)  # Ping in milliseconds
            if not ping_:
                self.user.is_online = False
                self.user.ping = -1.0

            if not self.user.is_online:
                self.user.is_online = True
            self.user.ping = ping_

            gevent.sleep(config['ping_interval'])

    def handle(self, sock, user):
        self.user = user
        self._ping = gevent.spawn(self.ping)
        return super().handle(sock)

    @db_session
    def disconnect(self):
        self._ping.kill()
        self._ping = None
        self.user.set_offline()
        return super().disconnect()

    def process_data(self, data):
        data = super().process_data(data)
        data['__params']['user'] = self.user  # Add user to params
        return data

    def process_incoming_request(self, request):
        if not {'__id', '__method', '__params'}.issubset(request.keys()):
            self.disconnect()
            return

        id_ = request['__id']

        self.pending_incoming_requests_threads.add(gevent.getcurrent())

        response = {
            '__id': id_,
            '__data': None,
            '__error': None
        }

        method_name = request['__method']

        if not hasattr(self.local_service, method_name):
            response['__error'] = 'Method not found'
        else:
            method = getattr(self.local_service, method_name)
            if not getattr(method, 'rpc', False):
                response['__error'] = 'Method not found'
            elif not getattr(method, 'permission', None) == 'user':  # Restrict down to user
                response['__error'] = 'Method not found'
            else:
                try:
                    response['__data'] = method(*request['__params'])
                except Exception as error:
                    response['__error'] = "%s: %s\n%s" % (error.__class__.__name__, error, error.__traceback__)

        try:
            data = json.dumps(response).encode('utf-8')
        except (TypeError, ValueError):
            return

        try:
            self._write(data)
        except OSError:
            return


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

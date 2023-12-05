from gevent import monkey
monkey.patch_all()

import signal
import os
import requests

from ping3 import ping
from flask import Flask, send_file
from werkzeug.utils import secure_filename
from flask_restful import Api, Resource, reqparse, request
from pony.orm import db_session

import gevent

from utilities.models import User, Printing
from utilities.config import config

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
api = Api(app)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000
app.config['UPLOAD_FOLDER'] = os.path.join('data', 'uploads')

@app.route('/')
def default():
    return 'Hello, World!'


def rpc_method_user(method):
    method.rpc = True
    method.permission = 'user'
    return method


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
        user = User.select(lambda u: u.username == username).first()

        if not user:
            return {'error': 'User not found'}, 404
        elif not user.verify_password(password):
            return {'error': 'Incorrect password'}, 401
        elif not os.path.exists(os.path.join('data', 'configs', f'{username}.conf')):
            return {'error': 'User configuration not found'}, 404

        # TODO: Return VPN configurations
        return send_file(os.path.join('..', '..', 'data', 'configs', f'{username}.conf'))


@api.resource('/print')
class Print(Resource):
    @db_session
    def post(self):
        ip = request.remote_addr
        user = User.select(lambda u: u.ip_address == ip).first()
        if not user:
            return {'error': 'User not found'}, 404

        file = request.files['file']
        if file.filename == '':
            return {'error': 'No file selected'}, 400

        if file:
            filename = f'{user.username}_{secure_filename(file.filename)}'
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            Printing(caller=user, source=filename)
            service_address = config['services']['PrintingService'][0]
            r = requests.post(f'http://{service_address[0]}:{service_address[1]}/print',
                              files={'file': open(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'rb')})
            return {'success': True}, 200
        else:
            return {'error': 'No file selected'}, 400


@api.resource('/performance')
class Performance(Resource):
    def __init__(self):
        super().__init__()
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('cpu', location='form')
        self.parser.add_argument('mem', location='form')

    @db_session
    def post(self):
        ip = request.remote_addr
        user = User.select(lambda u: u.ip_address == ip).first()
        if not user:
            return {'error': 'User not found'}, 404

        args = self.parser.parse_args()
        cpu = args['cpu'] or ""
        mem = args['mem'] or ""
        user.cpu = cpu
        user.ram = mem
        return {'success': True}, 200


def ping_users():
    while True:
        with db_session:
            users = User.select()
            batch_size = 5
            batch = []
            for i in range(0, len(users), batch_size):
                # Create a gevnet batch
                batch.append(gevent.spawn(ping_batch, users[i:i + batch_size]))
            gevent.joinall(batch)
        print("DONE")


def ping_batch(batch):
    with db_session:
        for user in batch:
            try:
                ping_ = ping(user.ip_address)
            except:
                ping_ = False
            if not ping_:
                user.is_online = False
                user.ping = -1.0
            else:
                user.is_online = True
                user.ping = round(ping_ * 1000.0, 2)


@api.resource('/user/<string:username>')
class UserInfo(Resource):
    def __init__(self):
        super().__init__()

    def get(self, username):
        with db_session:
            user = User.select(lambda u: u.username == username).first()
            if not user:
                return {'error': 'User not found'}, 404
            return {'username': user.username, 'ip_address': user.ip_address, 'is_online': user.is_online}, 200


def exit():
    os._exit(0)


ping_thread = None
gevent.signal_handler(signal.SIGINT, exit)

def main():
    global ping_thread
    ping_thread = gevent.spawn(ping_users)

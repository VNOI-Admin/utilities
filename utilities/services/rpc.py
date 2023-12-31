import functools
import uuid
import json
import socket
from weakref import WeakSet

import gevent
import gevent.socket
import gevent.lock
import gevent.event

from ..config import get_service_address


class RPCError(Exception):
    pass


def rpc_method(method, permission=None):
    method.rpc = True
    method.permission = permission
    return method


class RPCServiceBase:
    MAX_MESSAGE_SIZE = 1024 * 1024  # 1 MB

    def __init__(self, remote_address):
        self._local_address = None
        self.remote_address = remote_address
        self._connection_event = gevent.event.Event()

        self._on_connect_handlers = list()
        self._on_disconnect_handlers = list()

        self._socket = None
        self._reader = None
        self._writer = None

        self._read_lock = gevent.lock.RLock()
        self._write_lock = gevent.lock.RLock()

    @property
    def connected(self):
        return self._connection_event.is_set()

    def add_on_connect_handler(self, handler):
        self._on_connect_handlers.append(handler)

    def add_on_disconnect_handler(self, handler):
        self._on_disconnect_handlers.append(handler)

    def initialize(self, sock, plus):
        if self.connected:
            raise RuntimeError('Service already connected')

        self._socket = sock
        self._reader = sock.makefile('rb')
        self._writer = sock.makefile('wb')
        self._connection_event.set()

        self._local_address = "%s:%d" % self._socket.getsockname()[:2]

        for handler in self._on_connect_handlers:
            gevent.spawn(handler, plus)

    def finalize(self):
        if self.connected:
            return

        self._socket = None
        self._reader = None
        self._writer = None
        self._local_address = None
        self._connection_event.clear()

        for handler in self._on_disconnect_handlers:
            gevent.spawn(handler)

    def disconnect(self):
        if not self.connected:
            return False

        try:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
        except OSError:
            pass
        finally:
            self.finalize()

        return True

    def _read(self):
        if not self.connected:
            raise OSError('Service not connected')

        try:
            with self._read_lock:
                if not self.connected:
                    raise OSError('Service not connected')
                data = self._reader.readline(self.MAX_MESSAGE_SIZE)

                if len(data) > 0 and not data.endswith(b'\r\n'):
                    raise OSError('Message too long')
        except OSError as error:
            if self.connected:
                raise error
            else:
                return b""

        return data

    def _write(self, data):
        if not self.connected:
            raise OSError('Service not connected')

        if len(data + b'\r\n') > self.MAX_MESSAGE_SIZE:
            raise OSError('Message too long')

        try:
            with self._write_lock:
                if not self.connected:
                    raise OSError('Service not connected')
                self._writer.write(data + b'\r\n')
                self._writer.flush()
        except OSError as error:
            self.finalize()
            raise error


class RPCServiceServer(RPCServiceBase):
    def __init__(self, local_service, remote_address):
        super().__init__(remote_address)
        self.local_service = local_service

        self.pending_incoming_requests_threads = WeakSet()

    def finalize(self):
        super().finalize()

        for thread in self.pending_incoming_requests_threads:
            thread.kill(RPCError(), block=False)

        self.pending_incoming_requests_threads.clear()

    def handle(self, sock):
        self.initialize(sock, self.remote_address)
        self.run()

    def run(self):
        while True:
            try:
                data = self._read()
            except OSError:
                break

            if len(data) == 0:
                self.finalize()
                break

            gevent.spawn(self.process_data, data)

    def process_data(self, data):
        try:
            message = json.loads(data.decode('utf-8'))
        except ValueError:
            self.disconnect()
            return

        self.process_incoming_request(message)

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


class RPCServiceClient(RPCServiceBase):
    def __init__(self, remove_service_cord, auto_retry=None):
        super().__init__(get_service_address(remove_service_cord))

        self.remote_service_cord = remove_service_cord

        self.pending_outgoing_requests = dict()
        self.pending_outgoing_requests_results = dict()

        self.auto_retry = auto_retry

        self._loop = None

    def finalize(self):
        super().finalize()

        for result in self.pending_outgoing_requests_results.values():
            result.set_exception(RPCError())

        self.pending_outgoing_requests.clear()
        self.pending_outgoing_requests_results.clear()

    def _connect(self):
        try:
            addresses = gevent.socket.getaddrinfo(
                self.remote_address.host,
                self.remote_address.port,
                type=gevent.socket.SOCK_STREAM
            )
        except socket.gaierror:
            raise

        for family, type, proto, _canonname, sockaddr in addresses:
            try:
                host, port, *rest = sockaddr
                sock = socket.socket(family, type, proto)
                sock.connect(sockaddr)
            except OSError:
                continue
            else:
                self.initialize(sock, self.remote_address)
                break

    def _run(self):
        while True:
            self._connect()
            while not self.connected and self.auto_retry is not None:
                gevent.sleep(self.auto_retry)
                self._connect()
            if self.connected:
                self.run()
            if self.auto_retry is None:
                break

    def connect(self):
        if self._loop is not None and not self._loop.ready():
            raise RuntimeError('Service already (re)connecting')
        self._loop = gevent.spawn(self._run)

    def disconnect(self):
        if super().disconnect():
            self._loop.kill()
            self._loop = None

    def run(self):
        while True:
            try:
                data = self._read()
            except OSError:
                break

            if len(data) == 0:
                self.finalize()
                break

            gevent.spawn(self.process_data, data)

    def process_data(self, data):
        try:
            message = json.loads(data.decode('utf-8'))
        except ValueError:
            self.disconnect()
            return

        self.process_incoming_response(message)

    def process_incoming_response(self, response):
        if not {'__id', '__data', '__error'}.issubset(response.keys()):
            self.disconnect()
            return

        id_ = response['__id']

        if id_ not in self.pending_outgoing_requests:
            return

        request = self.pending_outgoing_requests.pop(id_)
        result = self.pending_outgoing_requests_results.pop(id_)
        error = response['__error']

        if error is not None:
            error_msg = "%s signaled RPC for %s: %s" % (self.remote_address, request['__method'], error)
            result.set_exception(RPCError(error_msg))
        else:
            result.set(response['__data'])

    def execute_rpc(self, method, data):
        id_ = uuid.uuid4().hex

        request = {
            '__id': id_,
            '__method': method,
            '__params': data
        }

        result = gevent.event.AsyncResult()

        try:
            data = json.dumps(request).encode('utf-8')
        except (TypeError, ValueError):
            result.set_exception(RPCError('JSON serialization error'))
            return result

        try:
            self._write(data)
        except OSError:
            result.set_exception(RPCError('Write error'))
            return result

        self.pending_outgoing_requests[id_] = request
        self.pending_outgoing_requests_results[id_] = result

        return result

    def __getattr__(self, method):
        def run_callback(func, plus, result):
            data = result.value
            error = None if result.successful() else "%s" % result.exception
            try:
                if plus is None:
                    func(data, error=error)
                else:
                    func(data, plus, error=error)
            except Exception:
                pass

        def remote_method(**data):
            callback = data.pop("callback", None)
            plus = data.pop("plus", None)
            result = self.execute_rpc(method, data)
            if callback is not None:
                callback = functools.partial(run_callback, callback, plus)
                result.rawlink(functools.partial(gevent.spawn, callback))
            return result

        return remote_method

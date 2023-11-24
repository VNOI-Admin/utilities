from gevent import monkey
monkey.patch_all()

from utilities.services.printing import app  # noqa: E402
from utilities.config import get_service_address, ServiceCoord

if __name__ == '__main__':
    host, port = get_service_address(ServiceCoord('PrintingService', 0))
    app.run(host=host, port=port)

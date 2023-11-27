from gevent import monkey
monkey.patch_all()

from utilities.config import config, Address, ServiceCoord
from utilities.services.user import app, main

if __name__ == '__main__':
    main()
    host, port = config["api"]
    app.run(host=host, port=port)

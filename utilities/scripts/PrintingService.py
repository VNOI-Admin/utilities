from gevent import monkey
monkey.patch_all()

from utilities.services.printing import PrintingService  # noqa: E402

if __name__ == '__main__':
    service = PrintingService()
    print(service.run())

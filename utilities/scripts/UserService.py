from gevent import monkey
monkey.patch_all()

from utilities.services.user import UserService  # noqa: E402

if __name__ == '__main__':
    service = UserService()
    print(service.run())

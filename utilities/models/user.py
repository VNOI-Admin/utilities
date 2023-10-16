import bcrypt

from . import db

from pony.orm import Required, Set


class User(db.Entity):
    username = Required(str, unique=True)
    password = Required(str)
    ip_address = Required(str, unique=True)  # IP address of the user.
    is_online = Required(bool, default=False)  # Whether the user is online.
    printings = Set("Printing")  # Printings that the user has made.

    def __repr__(self):
        return f'<User {self.username}>'

    def before_insert(self):
        self.password = "bcrypt:" + bcrypt.hashpw(self.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def verify_password(self, password):
        if self.password.startswith('bcrypt:'):
            return bcrypt.checkpw(password.encode('utf-8'), self.password[7:].encode('utf-8'))
        else:
            return False

    def before_update(self):
        if not self.password.startswith('bcrypt:'):
            self.password = "bcrypt:" + bcrypt.hashpw(self.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

from . import db

from pony.orm import Required


class Printing(db.Entity):
    caller = Required("User")
    source = Required(str)

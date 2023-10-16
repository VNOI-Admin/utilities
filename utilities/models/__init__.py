from pony.orm import Database

db = Database()
db.bind(provider='sqlite', filename='../database.sqlite', create_db=True)

# Import all models here
from .user import User  # noqa: E402
from .printing import Printing  # noqa: E402

db.generate_mapping(create_tables=True)

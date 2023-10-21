from pony.orm import Database

from utilities.config import config

db = Database()
db.bind(provider='sqlite', filename=config['database'], create_db=True)

# Import all models here
from .user import User  # noqa: E402
from .printing import Printing  # noqa: E402

db.generate_mapping(create_tables=True)

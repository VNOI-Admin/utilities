from pony.orm import Database

db = Database()
db.bind(provider='sqlite', filename='database.sqlite', create_db=True)

# Import all models here

db.generate_mapping(create_tables=True)

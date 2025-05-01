from sqlalchemy import create_engine
from models import Base


DATABASE_URL = "postgresql+psycopg2://myuser:mypassword@localhost:5432/mydb"

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)

print("Tables created successfully.")

from backend import create_app

from extensions import db

app = create_app()

with app.app_context():

    db.create_all()

    print("WorldMap Live database initialized.")

    print("Tables created successfully.")



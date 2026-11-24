import os

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import URL

db = SQLAlchemy()


def init_database(app):
    password = os.getenv("HOMER_DB_PASSWORD")

    if not password:
        raise RuntimeError(
            "Не задана переменная окружения HOMER_DB_PASSWORD."
        )

    database_url = URL.create(
        drivername="postgresql+psycopg2",
        username="postgres",
        password=password,
        host="localhost",
        port=5432,
        database="homer_db"
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

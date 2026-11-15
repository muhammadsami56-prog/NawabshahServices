import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get(
        'SECRET_KEY',
        'development-only-secret-key'
    )

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'mysql+pymysql://root:@localhost/nawabshah_services'
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
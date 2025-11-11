from pymongo import MongoClient
from django.conf import settings
import os

def get_database():
    # Get the database connection details from environment variables
    db_host = os.getenv('GLOBAL_DB_HOST', 'localhost')
    db_port = int(os.getenv('GLOBAL_DB_PORT', 27017))
    db_name = os.getenv('STORETRUST_DB_NAME', 'StoreTrust')

    client = MongoClient(host=db_host, port=db_port)
    db = client[db_name]
    return db
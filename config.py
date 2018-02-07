import os
from dotenv import load_dotenv


dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

db_credentials = {
    'dev': {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': os.environ.get('DB_PORT', 3306),
        'user': os.environ.get('DB_USERNAME'),
        'passwd': os.environ.get('DB_PASSWORD'),
        'db': os.environ.get('DB_DATABASE', 'fdm_test'),
    },
    'prod': {

    },
}

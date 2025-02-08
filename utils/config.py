import os
#from dotenv import load_dotenv
#load_dotenv()

PROJECT_ID = 'iqright'
SECRET_KEY = 'iqrightapp_secret'
SECURITY_PASSWORD_SALT = 'iqrightapp_salt'
DEBUG = True
OFFLINE_USERS_FILENAME = 'offline_users.iqr'
OFFLINE_FULL_LOAD_FILENAME = 'full_load.iqr'
LOCAL_FILE_VERSIONS = 'local_file_versions.json'

if os.getenv('LOCAL', None) == 'TRUE':
    API_URL = 'http://127.0.0.1:5001/api/'
    LORASERVICE_PATH = '.'
    LORASERVICE_LOG_PATH = './LoraService.log'
else:
    API_URL = 'https://integration.iqright.app/api/'
    LORASERVICE_PATH = '/etc/iqright/LoraService'
    LORASERVICE_LOG_PATH = '/etc/iqright/LoraService/LoraService.log'

TOPIC_PREFIX = 'Class'

TOPIC = ''

IDFACILITY = 1

BEACON_LOCATIONS = [
    {"idBeacon": 1, "beacon": "QR Reader", "location": "Gym Side"},
    {"idBeacon": 2, "beacon": "QR Reader", "location": "East Side"},
    {"idBeacon": 3, "beacon": "BLE Reader","location": "Main Entrance"}]


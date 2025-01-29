import os
#from dotenv import load_dotenv
#load_dotenv()

SECRET_KEY = 'iqrightapp_secret'
SECURITY_PASSWORD_SALT = 'iqrightapp_salt'

if os.getenv('LOCAL', None) == 'TRUE':
    API_URL = 'http://127.0.0.1:5001/api/'
else:
    API_URL = 'https://integration.iqright.app/api/'

TOPIC_PREFIX = 'Class'

TOPIC = ''

IDFACILITY = 1

BEACON_LOCATIONS = [
    {"idBeacon": 1, "beacon": "QR Reader", "location": "Gym Side"},
    {"idBeacon": 2, "beacon": "QR Reader", "location": "East Side"},
    {"idBeacon": 3, "beacon": "BLE Reader","location": "Main Entrance"}]


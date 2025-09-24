import os
#from dotenv import load_dotenv
#load_dotenv()

#Project Configuration
PROJECT_ID = 'iqright'
SECRET_KEY = 'iqrightapp_secret'
SECURITY_PASSWORD_SALT = 'iqrightapp_salt'
DEBUG = True
# HOME_DIR = os.environ['HOME']

#LOGGING Configuration
LOG_FILENAME = "IQRight_Daemon.debug"
MAX_LOG_SIZE = 20 * 1024 * 1024 #20Mb
BACKUP_COUNT = 10

#Offline Data Configuration
OFFLINE_USERS_FILENAME = 'offline_users.iqr'
OFFLINE_FULL_LOAD_FILENAME = 'full_load.iqr'
LOCAL_FILE_VERSIONS = 'local_file_versions.json'
FILE_DTYPE = {'ChildID': int, 'IDUser': int, 'FirstName': str, 'LastName': str, 'AppIDApprovalStatus': int \
                     , 'AppApprovalStatus': str, 'DeviceID': str, 'Phone': str, 'ChildName': str, 'ExternalNumber': str \
                     , 'HierarchyLevel1': str, 'HierarchyLevel1Type': str, 'HierarchyLevel1Desc': str \
                     , 'HierarchyLevel2': str, 'HierarchyLevel2Type': str, 'HierarchyLevel2Desc': str \
                     , 'StartDate': str, 'ExpireDate': str, 'IDApprovalStatus': int, 'ApprovalStatus': str
                     , 'MainContact': int, 'Relationship': str, 'IDHierarchy': int}

#API Configuration
API_TIMEOUT = 10.0
if os.getenv('DEBUGSERVICE', 'FALSE') == 'TRUE':
    API_URL = 'http://127.0.0.1:5001/api/'
else:
    API_URL = 'https://integration.iqright.app/api/'
if os.getenv('LOCAL', None) == 'TRUE':
    LORASERVICE_PATH = '.'
    LORASERVICE_LOG_PATH = './LoraService.log'
    HOME_DIR = '.'
else:
    LORASERVICE_PATH = '/etc/iqright/LoraService'
    LORASERVICE_LOG_PATH = '/etc/iqright/LoraService/LoraService.log'
    HOME_DIR = '/etc/iqright/LoraService'


#MQTT Configuration
TOPIC_PREFIX = 'Class'
TOPIC = ''
MQTT_BROKER = 'localhost'  # eg. choosen-name-xxxx.cedalo.cloud
MQTT_PORT = 1883
MQTT_USERNAME = 'iqright'
MQTT_TRANSPORT = 'tcp' #'websockets' # or 'tcp
MQTT_VERSION = '5' # or '3' 
MQTT_KEEPALIVE = 60

#LORA Configuration
RFM9X_FREQUENCE = 915.23
RFM9X_TX_POWER = 23
RFM9X_NODE = 1
RFM9X_ACK_DELAY = 0.1
RFM9X_SEND_DELAY = 0.3
RMF9X_POOLING = 0.9

#IQRight Configuration
IDFACILITY = 1
BEACON_LOCATIONS = [
    {"idBeacon": 1, "beacon": "QR Reader", "location": "Gym Side"},
    {"idBeacon": 2, "beacon": "QR Reader", "location": "East Side"},
    {"idBeacon": 3, "beacon": "BLE Reader","location": "Main Entrance"}]


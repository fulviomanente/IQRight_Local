import os
#from dotenv import load_dotenv
#load_dotenv()

#Project Configuration
PROJECT_ID = 'iqright'
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
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')  # eg. choosen-name-xxxx.cedalo.cloud
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
# MQTT credentials should be stored in encrypted credentials file, not here
# Use secure_credentials.get_secret('mqttUsername') and get_secret('mqttPassword')
MQTT_TRANSPORT = 'tcp' #'websockets' # or 'tcp
MQTT_VERSION = '5' # or '3'
MQTT_KEEPALIVE = 60

#MESHTASTIC Configuration
# Server configuration (main receiver - typically node ID 1)
MESHTASTIC_SERVER_NODE_ID = 1
MESHTASTIC_SERVER_NODE_NUM = 845261050
MESHTASTIC_SERVER_SERIAL_PORT = '/dev/ttyACM0'  # or /dev/ttyUSB0, check with: ls /dev/tty*

# Client configuration (scanners - typically node ID 102, 103, etc.)
MESHTASTIC_CLIENT_NODE_ID = 102  # This should be set per device
MESHTASTIC_CLIENT_SERIAL_PORT = '/dev/ttyACM0'  # or /dev/ttyUSB0

# Meshtastic mesh network settings
MESHTASTIC_REGION = 'US'  # or 'EU_868', 'EU_433', etc.
MESHTASTIC_MODEM_PRESET = 'LONG_FAST'  # Options: LONG_FAST, LONG_SLOW, MEDIUM_FAST, MEDIUM_SLOW, SHORT_FAST, SHORT_SLOW

#IQRight Configuration
IDFACILITY = 1
BEACON_LOCATIONS = [
    {"idBeacon": 373475968, "beacon": "QR Reader", "location": "Gym Side"},
    {"idBeacon": 103, "beacon": "QR Reader", "location": "Church Side"},
    {"idBeacon": 104, "beacon": "BLE Reader","location": "Church Side"}]


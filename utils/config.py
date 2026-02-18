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
                     , 'MainContact': int, 'Relationship': str, 'IDHierarchy': int, 'ClassCode': str}

#API Configuration
API_ENABLED = os.getenv('API_ENABLED', 'FALSE') == 'TRUE'
API_TIMEOUT = float(os.getenv('API_TIMEOUT', '10.0'))
LOOKUP_TIMEOUT = float(os.getenv('LOOKUP_TIMEOUT', '2.0'))
if os.getenv('DEBUGSERVICE', 'FALSE') == 'TRUE':
    API_URL = 'http://127.0.0.1:5001/api/'
else:
    API_URL = 'https://integration.iqright.app/api/'
if os.getenv('LOCAL', None) == 'TRUE':
    #LORASERVICE_PATH = '/Users/fulviomanente/Documents/Code/IQRight/Local/IQRight_Local/data'
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

#LORA Configuration (Legacy - kept for backwards compatibility)
RFM9X_FREQUENCE = 915.23
RFM9X_TX_POWER = 23
RFM9X_NODE = 1
RFM9X_ACK_DELAY = 0.1
RFM9X_SEND_DELAY = 0.3
RMF9X_POOLING = 0.9

# Enhanced LoRa Packet Configuration
LORA_NODE_TYPE = os.getenv('LORA_NODE_TYPE', 'SERVER')  # SERVER, SCANNER, REPEATER
LORA_NODE_ID = int(os.getenv('LORA_NODE_ID', '1'))  # 1=server, 100-199=scanners, 200-256=repeaters
LORA_FREQUENCY = float(os.getenv('LORA_FREQUENCY', '915.23'))  # MHz
LORA_TX_POWER = int(os.getenv('LORA_TX_POWER', '23'))  # dBm
LORA_TTL = int(os.getenv('LORA_TTL', '3'))  # Max hops for repeater
LORA_ENABLE_CA = os.getenv('LORA_ENABLE_CA', 'TRUE') == 'TRUE'  # Collision avoidance
LORA_CA_MIN_DELAY_MS = int(os.getenv('LORA_CA_MIN_DELAY_MS', '10'))
LORA_CA_MAX_DELAY_MS = int(os.getenv('LORA_CA_MAX_DELAY_MS', '100'))
LORA_RX_GUARD_MS = int(os.getenv('LORA_RX_GUARD_MS', '50'))

#MESHTASTIC Configuration
# Server configuration (main receiver - typically node ID 1)
MESHTASTIC_SERVER_NODE_ID = 1
MESHTASTIC_SERVER_HOST = 'localhost'
MESHTASTIC_SERVER_PORT = 4403

# Client configuration (scanners - typically node ID 102, 103, etc.)
MESHTASTIC_CLIENT_NODE_ID = 102  # This should be set per device
MESHTASTIC_CLIENT_HOST = 'localhost'
MESHTASTIC_CLIENT_PORT = 4403

# Meshtastic mesh network settings
MESHTASTIC_REGION = 'US'  # or 'EU_868', 'EU_433', etc.
MESHTASTIC_MODEM_PRESET = 'LONG_FAST'  # Options: LONG_FAST, LONG_SLOW, MEDIUM_FAST, MEDIUM_SLOW, SHORT_FAST, SHORT_SLOW

# Grade Restriction Configuration
RESTRICTED_GRADES = ['7th', '8th']
UNRESTRICTED_DATES = []

#IQRight Configuration
IDFACILITY = 1
BEACON_LOCATIONS = {
    102: {"device": "QR Reader", "location": "Gym Side"},
    103: {"device": "QR Reader", "location": "Gym Side"},
    2: {"device": "QR Reader", "location": "East Side"},
    3: {"device": "BLE Reader","location": "Main Entrance"}}


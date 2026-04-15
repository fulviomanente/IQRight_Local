import os

# Project Configuration
PROJECT_ID = 'iqright'
SECRET_KEY = 'iqrightapp_secret'
SECURITY_PASSWORD_SALT = 'iqrightapp_salt'
DEBUG = os.getenv('DEBUG', 'FALSE') == 'TRUE'

# LOGGING Configuration
LOG_FILENAME = "IQRight_Repeater.debug"
MAX_LOG_SIZE = 20 * 1024 * 1024  # 20Mb
BACKUP_COUNT = 10

# Offline Data Configuration
OFFLINE_USERS_FILENAME = 'offline_users.iqr'
OFFLINE_FULL_LOAD_FILENAME = 'full_load.iqr'
LOCAL_FILE_VERSIONS = 'local_file_versions.json'
FILE_DTYPE = {
    'ChildID': int, 'IDUser': int, 'FirstName': str, 'LastName': str, 'AppIDApprovalStatus': int,
    'AppApprovalStatus': str, 'DeviceID': str, 'Phone': str, 'ChildName': str, 'ExternalNumber': str,
    'HierarchyLevel1': str, 'HierarchyLevel1Type': str, 'HierarchyLevel1Desc': str,
    'HierarchyLevel2': str, 'HierarchyLevel2Type': str, 'HierarchyLevel2Desc': str,
    'StartDate': str, 'ExpireDate': str, 'IDApprovalStatus': int, 'ApprovalStatus': str,
    'MainContact': int, 'Relationship': str, 'IDHierarchy': int
}

# API Configuration
API_TIMEOUT = 10.0
if os.getenv('DEBUGSERVICE', 'FALSE') == 'TRUE':
    API_URL = 'http://127.0.0.1:5001/api/'
else:
    API_URL = 'https://integration.iqright.app/api/'

if os.getenv('LOCAL', None) == 'TRUE':
    LORASERVICE_PATH = './data'
    LORASERVICE_LOG_PATH = './log/Repeater.log'
    HOME_DIR = '.'
else:
    LORASERVICE_PATH = '/home/iqright/data'
    LORASERVICE_LOG_PATH = '/home/iqright/log/Repeater.log'
    HOME_DIR = '/home/iqright'

# MQTT Configuration
TOPIC_PREFIX = 'Class'
TOPIC = ''
MQTT_BROKER = 'localhost'
MQTT_PORT = 1883
MQTT_USERNAME = 'iqright'
MQTT_TRANSPORT = 'tcp'
MQTT_VERSION = '5'
MQTT_KEEPALIVE = 60

# Enhanced LoRa Packet Configuration
LORA_NODE_TYPE = 'REPEATER'
LORA_NODE_ID = int(os.getenv('LORA_NODE_ID', '200'))  # 200-256 for repeaters
LORA_FREQUENCY = float(os.getenv('LORA_FREQUENCY', '915.23'))  # MHz
LORA_TX_POWER = int(os.getenv('LORA_TX_POWER', '23'))  # dBm
LORA_TTL = int(os.getenv('LORA_TTL', '3'))  # Max hops for repeater
LORA_ENABLE_CA = os.getenv('LORA_ENABLE_CA', 'TRUE') == 'TRUE'  # Collision avoidance
LORA_CA_MIN_DELAY_MS = int(os.getenv('LORA_CA_MIN_DELAY_MS', '10'))
LORA_CA_MAX_DELAY_MS = int(os.getenv('LORA_CA_MAX_DELAY_MS', '100'))
LORA_RX_GUARD_MS = int(os.getenv('LORA_RX_GUARD_MS', '50'))

# Power Management HAT selection (WAVESHARE or PISUGAR)
POWER_HAT = os.getenv('POWER_HAT', 'WAVESHARE').upper()

# LoRa SPI pins — Waveshare HAT uses GPIO 7 and 25, so LoRa pins move to 17/16.
# PiSugar uses I2C only (no GPIO conflict), so standard CE1/D25 pins work.
if POWER_HAT == 'PISUGAR':
    LORA_CS_PIN = int(os.getenv('LORA_CS_PIN', '7'))     # CE1/GPIO 7 (standard)
    LORA_RST_PIN = int(os.getenv('LORA_RST_PIN', '25'))  # D25/GPIO 25 (standard)
else:
    LORA_CS_PIN = int(os.getenv('LORA_CS_PIN', '17'))     # GPIO 17 (moved for Waveshare)
    LORA_RST_PIN = int(os.getenv('LORA_RST_PIN', '16'))   # GPIO 16 (moved for Waveshare)

# Waveshare Power Management HAT GPIO pins
WAVESHARE_SHUTDOWN_PIN = 20  # HAT signals Pi to shutdown (input)
WAVESHARE_RUNNING_PIN = 21   # Pi tells HAT it's running (output)
WAVESHARE_SERIAL_DEVICE = '/dev/ttyS0'
WAVESHARE_SERIAL_BAUD = 115200

# IQRight Configuration
IDFACILITY = 1
BEACON_LOCATIONS = [
    {"idBeacon": 102, "beacon": "QR Reader", "location": "Gym Side"},
    {"idBeacon": 103, "beacon": "QR Reader", "location": "East Side"},
    {"idBeacon": 3, "beacon": "BLE Reader", "location": "Main Entrance"}
]

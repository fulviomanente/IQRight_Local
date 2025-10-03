# Import Python System Libraries
import time
import logging
import logging.handlers
import os
import json
from datetime import datetime
import pandas as pd
import asyncio
from utils.api_client import get_secret
import aiohttp
from dotenv import load_dotenv
from aiohttp import BasicAuth
from cryptography.fernet import Fernet
from io import StringIO

load_dotenv()

#Import Config
from utils.config import API_URL, API_TIMEOUT, DEBUG, LORASERVICE_PATH, OFFLINE_FULL_LOAD_FILENAME, HOME_DIR, FILE_DTYPE, \
    TOPIC, TOPIC_PREFIX, MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_TRANSPORT, MQTT_VERSION, MQTT_KEEPALIVE,   \
    LOG_FILENAME, MAX_LOG_SIZE, BACKUP_COUNT, RFM9X_FREQUENCE,   \
    RFM9X_SEND_DELAY, RFM9X_TX_POWER, RFM9X_NODE, RFM9X_ACK_DELAY, RMF9X_POOLING,\
    PROJECT_ID, BEACON_LOCATIONS, IDFACILITY
    

#Import MQ Libraries
import paho.mqtt.client as mqtt
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes

#Setup MQTT Topics
topicPrefix: bool = False
if TOPIC != '':
    Topic = TOPIC
elif TOPIC_PREFIX != '':
    Topic = TOPIC_PREFIX
    topicPrefix = True
else:
    Topic = 'IQSend'

CommandTopic = "IQRSend"

#GET Beacon Locations
beacon_locations_dict = beacon_locations_dict = {beacon_info["beacon"]: beacon_info for beacon_info in BEACON_LOCATIONS}

#Load Offline Full Load File
#df = pd.read_csv(f'{LORASERVICE_PATH}/{OFFLINE_FULL_LOAD_FILENAME}',
#                 dtype=FILE_DTYPE)


try:
    #LOGGING Setup ####################################################
    handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT)
    logging.basicConfig(filename=f'{HOME_DIR}/log/{LOG_FILENAME}')
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(log_formatter)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.DEBUG if DEBUG else logging.INFO)
    ######################################################################
except Exception as e:
    print(f'Error creating log object')
    print(e.__str__())


# Create the I2C interface.
# Import LORA Libraries - THIS WILL FAIL IN A NON RASPBERRY PI ENVIRONMENT
if os.environ.get("LOCAL") != 'TRUE':
    import busio
    from digitalio import DigitalInOut, Direction, Pull
    import board
    import adafruit_rfm9x
    i2c = busio.I2C(board.SCL, board.SDA)
    reset_pin = DigitalInOut(board.D4)
    # Configure LoRa Radio
    CS = DigitalInOut(board.CE1)
    RESET = DigitalInOut(board.D25)
    spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
    rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, RFM9X_FREQUENCE)
    rfm9x.tx_power = RFM9X_TX_POWER
    rfm9x.node = RFM9X_NODE
    rfm9x.ack_delay = RFM9X_ACK_DELAY
    prev_packet = None
    logging.info('Connected to Lora Module')
else:
    logging.info('Bypassing Lora Module')


client = mqtt.Client(client_id="IQRight_Daemon", transport=MQTT_TRANSPORT, protocol=mqtt.MQTTv5)
client.username_pw_set("IQRight", "123456")
 
properties=Properties(PacketTypes.CONNECT)
properties.SessionExpiryInterval=30*60 # in seconds
client.connect(MQTT_BROKER,
               port=MQTT_PORT,
               clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
               properties=properties,
               keepalive=MQTT_KEEPALIVE);
logging.info('Connected to MQTT Server')

lastCommand = None

def getGrade(strGrade: str):
    if strGrade == 'First Grade' or strGrade[0:2] == '01':
        return '1st'
    elif strGrade == 'Second Grade' or strGrade[0:2] == '02':
        return '2nd'
    elif strGrade == 'Third Grade' or strGrade[0:2] == '03':
        return '3rd'
    elif strGrade == 'Fourth Grade' or strGrade[0:2] == '04':
        return '4th'
    if strGrade == 'Fifth Grade' or strGrade[0:2] == '01':
        return '5th'
    elif strGrade == 'Sixth Grade' or strGrade[0:2] == '02':
        return '6th'
    elif strGrade == 'Seventh Grade' or strGrade[0:2] == '03':
        return '7th'
    elif strGrade == 'Eighth Grade' or strGrade[0:2] == '04':
        return '8th'
    elif strGrade[1] == 'K':
        return 'Kind'
    else:
        return 'N/A'


def openFile(filename: str, keyfilename: str ='offline.key'):
    """Opens and decrypts a file."""
    try:
        keyfilename = (LORASERVICE_PATH + '/' + keyfilename) if keyfilename else None
        if os.path.exists(filename):
            if keyfilename:
                return True, decrypt_file(datafile=filename, filename=keyfilename)
            else:
                return True, decrypt_file(datafile=filename)
        else:
            logging.critical(f"No local CSV file found at {filename}. Terminating.")
            return False, None
    except Exception as e:
        logging.error(f"Error opening file {filename}: {str(e)}")
        return False, None

def decrypt_file(datafile, filename: str ='offline.key'):
    """Decrypts a file containing an encrypted Pandas DataFrame."""
    try:
        with open(filename, 'rb') as key_file:
            key = key_file.read()
        f = Fernet(key)
        with open(datafile, 'rb') as encrypted_file:
            encrypted_data = encrypted_file.read()
        decrypted_data = f.decrypt(encrypted_data)
        df = pd.read_csv(StringIO(decrypted_data.decode('utf-8')))
        return df
    except FileNotFoundError as e:
        logging.error(f"File not found error: {str(e)}")
        return None
    except Exception as e:
        logging.error(f"Error decrypting file {datafile}: {str(e)}")
        return None


if os.path.exists(f"{LORASERVICE_PATH}/{OFFLINE_FULL_LOAD_FILENAME}"):
    status, df = openFile(filename=f"{LORASERVICE_PATH}/{OFFLINE_FULL_LOAD_FILENAME}")
    logging.info(f"{status}")
    logging.info(f"{df.size}")
else:
    logging.error("UNABLE TO OPEN USER FILE, EXITING")
    exit(1)

async def get_user_from_api(code):
    #try:
    async with aiohttp.ClientSession() as session:
        api_url = f"{API_URL}apiGetUserInfo"  # Replace with your actual API endpoint
        payload = {"searchCode": code}
        headers = {
            "Content-Type": "application/json",
            "accept": "application/json",
            "caller": "LocalApp",
            "idFacility": str(IDFACILITY)
        }

        # Debug logging
        logging.info(f"API URL: {api_url}")
        logging.info(f"Payload: {payload}")
        logging.info(f"Headers: {headers}")
        logging.info(f"Timeout: {API_TIMEOUT} seconds")
        
        apiUsername = get_secret('apiUsername')
        apiPassword = get_secret('apiPassword')

        if apiUsername and apiPassword:
            auth = BasicAuth(apiUsername["value"], apiPassword["value"])
            logging.info(f"Auth username: {apiUsername['value']}")
            
            try:
                logging.info("Attempting API call...")
                async with session.post(api_url, json=payload, timeout=API_TIMEOUT, headers=headers, auth=auth) as response:
                    print(f"Status: {response.status}")
                    print(await response.json())
                    if response.status == 200:
                        return await response.json()
                    else:
                        logging.error(f"API getUserAccess request failed with status: {response.status}")
                        return None
            except asyncio.TimeoutError:
                logging.error(f"API call timed out after {API_TIMEOUT} seconds")
                logging.error(f"Failed URL: {api_url}")
                return None
            except aiohttp.ClientError as e:
                logging.error(f"Client error during API call: {e}")
                logging.error(f"Failed URL: {api_url}")
                return None
            except Exception as e:
                logging.error(f"Unexpected error during API call: {e}")
                logging.error(f"Failed URL: {api_url}")
                return None
        else:
            logging.error("API getUserAccess request failed on getting secrets")
            return None
                
    #except asyncio.TimeoutError:
    #    logging.warning("API getUserAccess request timed out")
    #    return None
    #except aiohttp.ClientError as e:
    #    logging.error(f"API getUserAccess request error: {e}")
    #    return None


async def get_user_local(beacon, code, distance, df):
    if not code:  # Return early if code is missing
        logging.error(f'Empty string sent for conversion into MQTT Object')
        return None

    try:
        logging.debug(f'Student Lookup (Local)')
        matches = df.loc[df['DeviceID'] == code]
        if matches.empty:
            logging.debug(f"Couldn't find Code: {code} locally")
            return None  # Return None if not found locally
        else:
            results = []
            # Iterate through all matching rows
            for _, row in matches.iterrows():
                result = {
                    "name": row['ChildName'],
                    "hierarchyLevel2": row['HierarchyLevel2'],
                    "hierarchyLevel1": row['HierarchyLevel1'],
                    "hierarchyID": f"{int(row['IDHierarchy']):02d}",
                    "node": beacon,
                    "externalID": code,
                    "distance": abs(int(distance)),
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "externalNumber": row['ExternalNumber'],
                    "location": beaconLocator(beacon),
                    "source": "local"
                }
                results.append(result)
            return results
    except Exception as e:
        logging.error(f'Error converting local data: {e}')
        return None


async def getInfo(beacon, code, distance, df):
    api_task = asyncio.create_task(get_user_from_api(code))
    local_task = asyncio.create_task(get_user_local(beacon, code, distance, df))

    #try:
    api_result = await asyncio.wait_for(api_task, timeout=10.0)  # Wait for the API with a timeout
    if api_result:
        if not isinstance(api_result, list):
            api_result = [api_result]  # Convert single result to list
        for result in api_result:
            result["source"] = "api"
        logging.info("Using API results")
        return api_result
    #except asyncio.TimeoutError:
    #    logging.warning("API Timeout. Using local data if available.")
    #    pass  # Handle timeout (use local result if available)
    #except Exception as ex:
    #    logging.error(f'Error processing data: {ex}')
    #    return None

    local_result = await local_task  # Get the local result

    return local_result  # Return local data if API timed out

async def handleInfo(strInfo: str):
    global lastCommand
    ret = False
    payload = None
    if len(strInfo) > 5:
        beacon, payload, distance = strInfo.split('|')
        if payload.find(":") >= 0:
            strCmd, command = payload.split(":")
            if command != lastCommand:
                payload = {'command': command}
        else:
            sendObj = await getInfo(beacon, payload, distance, df)
            payload = sendObj if sendObj else None
        
        if payload:
            # Handle list of results
            if isinstance(payload, list):
                for item in payload:
                    time.sleep(RFM9X_SEND_DELAY)
                    if sendDataScanner(item) == False:
                        logging.error(f'FAILED to sent to Scanner: {json.dumps(item)}')
                    else:
                        sendObj = json.dumps(item)
                        logging.info(sendObj)
                        hierarchyID = str(item.get("hierarchyID", '00'))
                        if publishMQTT(sendObj, hierarchyID):
                            logging.info(' Message Sent')
                        else:
                            logging.error('MQTT ERROR')
            else:
                # Handle single command payload
                time.sleep(RFM9X_SEND_DELAY)
                if sendDataScanner(payload) == False:
                    logging.error(f'FAILED to sent to Scanner: {json.dumps(payload)}')
                else:
                    hierarchyID = str(payload.get("hierarchyID", '00'))
                    sendObj = json.dumps(payload)
                    logging.info(sendObj)
                    if publishMQTT(sendObj):
                        logging.info(' Message Sent')
                    else:
                        logging.error('MQTT ERROR')
    return True

def sendDataScanner(payload: dict):
    startTime = time.time()
    while True:
        if 'name' in payload:
            msg = f"{payload['name']}|{payload['hierarchyLevel1']}|{getGrade(payload['hierarchyLevel2'])}"
        else:
            msg = f"cmd|ack|{payload['command']}"
            print(msg)
        if rfm9x.send_with_ack(bytes(msg, "UTF-8")):
            logging.debug('Info sent back')
            return True
        else:
            logging.debug(f"Failed to send Data to node: {msg}")
        if time.time() >= startTime + 5:
            logging.error(f"Timeout trying to send Data to node: {msg}")
            return False

def publishMQTT(payload: str, hierarchyID: str = None):
    count = 5
    while count > 0:
        if sendMessageMQTT(payload, hierarchyID):
            return True
        else:
            count = count -1
            #IF failed, reconnect to MQTT Server
            client.disconnect()
            logging.info(f"Disconnected from MQTT")
            client.connect(MQTT_BROKER,
                   port=MQTT_PORT,
                   clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
                   properties=properties,
                   keepalive=MQTT_KEEPALIVE);
            logging.info('Connected to MQTT Server')
    return False

def sendMessageMQTT(payload: str, topicSufix: str = None):
    logging.info(f"Sending {payload} to MQTT")
    if topicPrefix and topicSufix:
        ret = client.publish(f'{Topic}{topicSufix}', payload)
    else:
        ret = client.publish(CommandTopic, payload)
    if ret[0] == 0:
        logging.debug(f'Message sent to Topic: {Topic}')
        logging.debug(f'Message ID {ret[1]}')
        return True
    else:
        logging.error(ret[0])
        logging.error(ret[1])
        logging.error('FAILED to sent to Topic: {Topic}')
        return False

def beaconLocator(idBeacon: int):
    if idBeacon in beacon_locations_dict:
        location = beacon_locations_dict[idBeacon]["location"]
        return location
    else:
        return ''

# Main Loop
if os.getenv("LOCAL") == 'TRUE':
    asyncio.run(handleInfo('102|123456789|1'))
else:
    while True:

        packet = None
        packet = rfm9x.receive(with_ack = True, with_header = True)
        if packet != None:
            prev_packet = packet[4:]
            print(prev_packet)
            try:
                packet_text = str(prev_packet, "utf-8")
            except Exception as e:
                logging.error(f'{prev_packet}: Invalid byte String')
                logging.error(f'{e.__str__()}')
                packet_text = None
            finally:
                if packet_text:
                    if DEBUG:
                        logging.debug(f'{packet} Received')
                        logging.debug(f'{packet_text} Converted to String')
                        logging.debug('RX: ')
                        logging.debug(packet_text)
                        #result, payload = handleInfo(packet_text)
                        asyncio.run(handleInfo(packet_text))

                    else:
                        logging.error('No response received from MQ Topic: IQSend or Empty Message received from Lora')
                else:
                    if DEBUG:
                        logging.debug('Empty Package Received')
                time.sleep(RMF9X_POOLING)

client.loop_forever();

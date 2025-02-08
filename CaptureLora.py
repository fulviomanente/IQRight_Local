# Import Python System Libraries
import time
import logging
import logging.handlers
import os
import json
from datetime import datetime
import pandas as pd
from utils.config import TOPIC_PREFIX, API_URL, IDFACILITY, LORASERVICE_PATH, OFFLINE_FULL_LOAD_FILENAME, TOPIC, TOPIC_PREFIX
import asyncio
import aiohttp
from google.cloud import secretmanager

# Import LORA Libraries
import busio
from digitalio import DigitalInOut, Direction, Pull
import board
# Import RFM9x
import adafruit_rfm9x

#Import MQ Libraries
import paho.mqtt.client as mqtt
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes

def get_secret(secret, expected: str = None, compare: bool = False):
    # Replace with your actual Secret Manager project ID and secret name
    project_id = os.getenv('PROJECT_ID')
    secret_name = secret
    secretValue: str = None
    result: bool = False
    try:
        # Create the Secret Manager client.
        client = secretmanager.SecretManagerServiceClient()
        # Build the resource name of the secret version.
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        # Access the secret version.
        secretValue = client.access_secret_version(name=name)
        if compare and expected:
            if secret == expected:
                result = True
            else:
                result = False
            secretValue = None
    except Exception as e:
        logging.debug(f'Error getting secret {secret} from envinronment')
        logging.debug(str(e))
    finally:
        response = {'value': secretValue.payload.data.decode('UTF-8'), 'result': result}
    return response

topicPrefix: bool = False
if TOPIC != '':
    Topic = TOPIC
elif TOPIC_PREFIX != '':
    Topic = TOPIC_PREFIX
    topicPrefix = True
else:
    Topic = 'IQSend'

beacon_locations_dict = beacon_locations_dict = {beacon_info["beacon"]: beacon_info for beacon_info in BEACON_LOCATIONS}
homeDir = os.environ['HOME']


df = pd.read_csv(f'{LORASERVICE_PATH}/{OFFLINE_FULL_LOAD_FILENAME}',
                 dtype={'ChildID': int, 'IDUser': int, 'FirstName': str, 'LastName': str, 'AppIDApprovalStatus': int \
                     , 'AppApprovalStatus': str, 'DeviceID': str, 'Phone': str, 'ChildName': str, 'ExternalNumber': str \
                     , 'HierarchyLevel1': str, 'HierarchyLevel1Type': str, 'HierarchyLevel1Desc': str \
                     , 'HierarchyLevel2': str, 'HierarchyLevel2Type': str, 'HierarchyLevel2Desc': str \
                     , 'StartDate': str, 'ExpireDate': str, 'IDApprovalStatus': int, 'ApprovalStatus': str
                     , 'MainContact': int, 'Relationship': str, 'IDHierarchy': int})


try:
    #LOGGING Setup ####################################################
    log_filename = "IQRight_Daemon.debug"
    max_log_size = 20 * 1024 * 1024 #20Mb
    backup_count = 10
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    #if os.environ.get("DEBUG"):
    debug = True
    handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=max_log_size, backupCount=backup_count)
    logging.basicConfig(filename=f'{homeDir}/log/{log_filename}')

    #else:
    #    debug = False
    #    logging.basicConfig(filename="IQRight_Daemon.log"), level=logging.INFO)

    handler.setFormatter(log_formatter)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)
    ######################################################################
except Exception as e:
    print(f'Error creating log object')
    print(e.__str__())


# Create the I2C interface.
i2c = busio.I2C(board.SCL, board.SDA)
reset_pin = DigitalInOut(board.D4)
# Configure LoRa Radio
CS = DigitalInOut(board.CE1)
RESET = DigitalInOut(board.D25)
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, 915.23)
rfm9x.tx_power = 23
rfm9x.node = 1
rfm9x.ack_delay = 0.1
prev_packet = None
logging.info('Connected to Lora Module')
version = '5' # or '3' 
mytransport = 'tcp' #'websockets' # or 'tcp

client = mqtt.Client(client_id="IQRight_Daemon", transport=mytransport, protocol=mqtt.MQTTv5)
client.username_pw_set("IQRight", "123456")
 
broker = '127.0.0.1' # eg. choosen-name-xxxx.cedalo.cloud
myport = 1883
properties=Properties(PacketTypes.CONNECT)
properties.SessionExpiryInterval=30*60 # in seconds
client.connect(broker,
               port=myport,
               clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
               properties=properties,
               keepalive=60);
logging.info('Connected to MQTT Server')

lastCommand = None



def getGrade(strGrade: str):
    if strGrade == 'First Grade':
        return '1st'
    elif strGrade == 'Second Grade':
        return '2nd'
    elif strGrade == 'Third Grade':
        return '3rd'
    elif strGrade == 'Fourth Grade':
        return '4th'
    else:
        return 'Kind'


async def get_user_from_api(code):
    try:
        async with aiohttp.ClientSession() as session:
            api_url = f"{API_URL}/UserAccess"  # Replace with your actual API endpoint
            payload = {"searchCode": code}
            headers = {
                "Content-Type": "application/json",
                "accept": "application/json",
                "caller": "LocalApp",
                "idFacility": IDFACILITY
            }

            apiUsername = get_secret('apiUsername')
            apiPassword = get_secret('apiPassword')

            auth = (apiUsername["value"], apiPassword["value"])

            async with session.post(api_url, json=payload, timeout=1.0, headers=headers, auth=auth) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logging.error(f"API getUserAccess request failed with status: {response.status}")
                    return None
    except asyncio.TimeoutError:
        logging.warning("API getUserAccess request timed out")
        return None
    except aiohttp.ClientError as e:
        logging.error(f"API getUserAccess request error: {e}")
        return None


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
                    "hierarchyID": row['HierarchyID'],
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

    try:
        api_result = await asyncio.wait_for(api_task, timeout=1.0)  # Wait for the API with a timeout
        if api_result:
            if not isinstance(api_result, list):
                api_result = [api_result]  # Convert single result to list
            for result in api_result:
                result["source"] = "api"
            logging.info("Using API results")
            return api_result
    except asyncio.TimeoutError:
        logging.warning("API Timeout. Using local data if available.")
        pass  # Handle timeout (use local result if available)
    except Exception as ex:
        logging.error(f'Error processing data: {ex}')
        return None

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
                    time.sleep(0.3)
                    if sendDataScanner(item) == False:
                        logging.error(f'FAILED to sent to Scanner: {json.dumps(item)}')
                    else:
                        sendObj = json.dumps(item)
                        logging.info(sendObj)
                        if publishMQTT(sendObj):
                            logging.info(' Message Sent')
                        else:
                            logging.error('MQTT ERROR')
            else:
                # Handle single command payload
                time.sleep(0.3)
                if sendDataScanner(payload) == False:
                    logging.error(f'FAILED to sent to Scanner: {json.dumps(payload)}')
                else:
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
            msg = f"{payload['name']}|{getGrade(payload['level1'])}|{payload['level2']}"
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

def publishMQTT(payload: str):
    count = 5
    while count > 0:
        if sendMessageMQTT(payload, str(payload.get("hierarchyID", '00'))):
            return True
        else:
            count = count -1
            #IF failed, reconnect to MQTT Server
            client.disconnect()
            logging.info(f"Disconnected from MQTT")
            client.connect(broker,
                   port=myport,
                   clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
                   properties=properties,
                   keepalive=60);
            logging.info('Connected to MQTT Server')
    return False

def sendMessageMQTT(payload: str, topicSufix: str = None):
    logging.info(f"Sending {payload} to MQTT")
    if topicPrefix and topicSufix:
        ret = client.publish(f'{Topic}{topicSufix}', payload)
    else:
        ret = client.publish(Topic, payload)
    if ret[0] == 0:
        logging.debug('Message sent to Topic: {Topic}')
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

#Main Loop
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
                if debug:
                    logging.debug(f'{packet} Received')
                    logging.debug(f'{packet_text} Converted to String')
                    logging.debug('RX: ')
                    logging.debug(packet_text)
                    #result, payload = handleInfo(packet_text)
                    asyncio.run(handleInfo(packet_text))

                else:
                    logging.error('No response received from MQ Topic: IQSend or Empty Message received from Lora')
            else:
                if debug:
                    logging.debug('Empty Package Received')
            time.sleep(0.9)


client.loop_forever();

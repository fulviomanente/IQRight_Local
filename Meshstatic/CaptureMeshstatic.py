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
import meshtastic
import meshtastic.tcp_interface
from pubsub import pub

load_dotenv()

#Import Config
from utils.config import API_URL, API_TIMEOUT, DEBUG, LORASERVICE_PATH, OFFLINE_FULL_LOAD_FILENAME, HOME_DIR, \
    TOPIC, TOPIC_PREFIX, MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_TRANSPORT, MQTT_VERSION, MQTT_KEEPALIVE,   \
    LOG_FILENAME, MAX_LOG_SIZE, BACKUP_COUNT, BEACON_LOCATIONS, IDFACILITY, \
    MESHTASTIC_SERVER_HOST, MESHTASTIC_SERVER_PORT, MESHTASTIC_SERVER_NODE_ID

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

FILEPATH = LORASERVICE_PATH + '/data/'

#GET Beacon Locations
beacon_locations_dict = {beacon_info["beacon"]: beacon_info for beacon_info in BEACON_LOCATIONS}

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

# Meshtastic Interface - Connect to local meshtasticd daemon via TCP
mesh_interface = None
if os.environ.get("LOCAL") != 'TRUE':
    try:
        mesh_interface = meshtastic.tcp_interface.TCPInterface(hostname=MESHTASTIC_SERVER_HOST)
        logging.info(f'Connected to Meshtastic daemon at {MESHTASTIC_SERVER_HOST}:{MESHTASTIC_SERVER_PORT}')
        logging.info(f'Server Node ID: {MESHTASTIC_SERVER_NODE_ID}')
    except Exception as e:
        logging.error(f'Failed to connect to Meshtastic daemon: {e}')
        exit(1)
else:
    logging.info('Bypassing Meshtastic Module (LOCAL mode)')

mqtt_client = mqtt.Client(client_id="IQRight_Daemon", transport=MQTT_TRANSPORT, protocol=mqtt.MQTTv5)
mqtt_client.username_pw_set("IQRight", "123456")

properties=Properties(PacketTypes.CONNECT)
properties.SessionExpiryInterval=30*60 # in seconds
mqtt_client.connect(MQTT_BROKER,
               port=MQTT_PORT,
               clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
               properties=properties,
               keepalive=MQTT_KEEPALIVE)
logging.info('Connected to MQTT Server')

lastCommand = None
pending_responses = {}

def getGrade(strGrade: str):
    if strGrade == 'First Grade' or strGrade[0:2] == '01':
        return '1st'
    elif strGrade == 'Second Grade' or strGrade[0:2] == '02':
        return '2nd'
    elif strGrade == 'Third Grade' or strGrade[0:2] == '03':
        return '3rd'
    elif strGrade == 'Fourth Grade' or strGrade[0:2] == '04':
        return '4th'
    elif strGrade == 'Fifth Grade' or strGrade[0:2] == '05':
        return '5th'
    elif strGrade == 'Sixth Grade' or strGrade[0:2] == '06':
        return '6th'
    elif strGrade == 'Seventh Grade' or strGrade[0:2] == '07':
        return '7th'
    elif strGrade == 'Eighth Grade' or strGrade[0:2] == '08':
        return '8th'
    elif strGrade[1] == 'K':
        return 'Kind'
    else:
        return 'N/A'

def openFile(filename: str, keyfilename: str ='offline.key'):
    """Opens and decrypts a file."""
    try:
        keyfilename = (FILEPATH + keyfilename) if keyfilename else None
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

if os.path.exists(f"{FILEPATH}/{OFFLINE_FULL_LOAD_FILENAME}"):
    status, df = openFile(filename=f"{FILEPATH}/{OFFLINE_FULL_LOAD_FILENAME}")
    logging.info(f"{status}")
    logging.info(f"{df.size}")
else:
    logging.error("UNABLE TO OPEN USER FILE, EXITING")
    exit(1)

async def get_user_from_api(code):
    async with aiohttp.ClientSession() as session:
        api_url = f"{API_URL}apiGetUserInfo"
        payload = {"searchCode": code}
        headers = {
            "Content-Type": "application/json",
            "accept": "application/json",
            "caller": "LocalApp",
            "idFacility": str(IDFACILITY)
        }

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

async def get_user_local(beacon, code, distance, df):
    if not code:
        logging.error(f'Empty string sent for conversion into MQTT Object')
        return None

    try:
        logging.debug(f'Student Lookup (Local)')
        matches = df.loc[df['DeviceID'] == code]
        if matches.empty:
            logging.debug(f"Couldn't find Code: {code} locally")
            return None
        else:
            results = []
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

    api_result = await asyncio.wait_for(api_task, timeout=10.0)
    if api_result:
        if not isinstance(api_result, list):
            api_result = [api_result]
        for result in api_result:
            result["source"] = "api"
        logging.info("Using API results")
        return api_result

    local_result = await local_task
    return local_result

async def handleInfo(strInfo: str, source_node: int):
    global lastCommand
    ret = False
    payload = None

    if len(strInfo) > 5:
        beacon, payload_code, distance = strInfo.split('|')

        if payload_code.find(":") >= 0:
            strCmd, command = payload_code.split(":")
            if command != lastCommand:
                payload = {'command': command}
        else:
            sendObj = await getInfo(beacon, payload_code, distance, df)
            payload = sendObj if sendObj else None

        if payload:
            # Handle list of results
            if isinstance(payload, list):
                for item in payload:
                    time.sleep(0.3)  # Small delay between messages
                    if sendDataScanner(item, source_node) == False:
                        logging.error(f'FAILED to send to Scanner: {json.dumps(item)}')
                    else:
                        sendObj = json.dumps(item)
                        logging.info(sendObj)
                        hierarchyID = str(item.get("hierarchyID", '00'))
                        if publishMQTT(sendObj, hierarchyID):
                            logging.info(' Message Sent to MQTT')
                        else:
                            logging.error('MQTT ERROR')
            else:
                # Handle single command payload
                time.sleep(0.3)
                if sendDataScanner(payload, source_node) == False:
                    logging.error(f'FAILED to send to Scanner: {json.dumps(payload)}')
                else:
                    hierarchyID = str(payload.get("hierarchyID", '00'))
                    sendObj = json.dumps(payload)
                    logging.info(sendObj)
                    if publishMQTT(sendObj):
                        logging.info(' Message Sent to MQTT')
                    else:
                        logging.error('MQTT ERROR')
    return True

def sendDataScanner(payload: dict, destination_node: int):
    """Send data back to scanner via Meshtastic with acknowledgment"""
    try:
        if 'name' in payload:
            msg = f"{payload['name']}|{payload['hierarchyLevel1']}|{getGrade(payload['hierarchyLevel2'])}"
        else:
            msg = f"cmd|ack|{payload['command']}"
            print(msg)

        logging.debug(f'Sending to node {destination_node}: {msg}')

        # Send with acknowledgment using Meshtastic
        mesh_interface.sendText(
            text=msg,
            destinationId=destination_node,
            wantAck=True
        )

        logging.info(f'Info sent back to node {destination_node}')
        return True

    except Exception as e:
        logging.error(f"Failed to send data to node {destination_node}: {msg} - Error: {e}")
        return False

def publishMQTT(payload: str, hierarchyID: str = None):
    count = 5
    while count > 0:
        if sendMessageMQTT(payload, hierarchyID):
            return True
        else:
            count = count - 1
            #IF failed, reconnect to MQTT Server
            mqtt_client.disconnect()
            logging.info(f"Disconnected from MQTT")
            mqtt_client.connect(MQTT_BROKER,
                   port=MQTT_PORT,
                   clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
                   properties=properties,
                   keepalive=MQTT_KEEPALIVE)
            logging.info('Connected to MQTT Server')
    return False

def sendMessageMQTT(payload: str, topicSufix: str = None):
    logging.info(f"Sending {payload} to MQTT")
    if topicPrefix and topicSufix:
        ret = mqtt_client.publish(f'{Topic}{topicSufix}', payload)
    else:
        ret = mqtt_client.publish(CommandTopic, payload)
    if ret[0] == 0:
        logging.debug(f'Message sent to Topic: {Topic}')
        logging.debug(f'Message ID {ret[1]}')
        return True
    else:
        logging.error(ret[0])
        logging.error(ret[1])
        logging.error('FAILED to send to Topic: {Topic}')
        return False

def beaconLocator(idBeacon: int):
    if idBeacon in beacon_locations_dict:
        location = beacon_locations_dict[idBeacon]["location"]
        return location
    else:
        return ''

def onReceive(packet, interface):
    """Callback for received Meshtastic messages"""
    try:
        # Check if this is a text message
        if 'decoded' in packet and 'text' in packet['decoded']:
            message_text = packet['decoded']['text']
            source_node = packet['from']

            logging.info(f"Received from node {source_node}: {message_text}")

            # Process the message asynchronously
            asyncio.run(handleInfo(message_text, source_node))

    except Exception as e:
        logging.error(f"Error processing received packet: {e}")
        logging.error(f"Packet: {packet}")

def onConnection(interface, topic=pub.AUTO_TOPIC):
    """Callback when Meshtastic connection is established"""
    logging.info("Meshtastic connection established")
    logging.info(f"My node info: {interface.myInfo}")

# Subscribe to Meshtastic events
if mesh_interface:
    pub.subscribe(onReceive, "meshtastic.receive.text")
    pub.subscribe(onConnection, "meshtastic.connection.established")
    logging.info("Subscribed to Meshtastic events")

# Main Loop
if os.getenv("LOCAL") == 'TRUE':
    asyncio.run(handleInfo('102|123456789|1', 102))
else:
    logging.info("Starting Meshtastic server listener...")
    logging.info("Waiting for messages from scanners...")

    # Keep the script running to receive messages
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
        if mesh_interface:
            mesh_interface.close()
        mqtt_client.disconnect()

mqtt_client.loop_forever()

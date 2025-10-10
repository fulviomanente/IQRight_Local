# Import Python System Libraries
import time
import logging
import logging.handlers
import os
import json
from datetime import datetime
import pandas as pd
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from utils.secure_credentials import get_secret
from dotenv import load_dotenv
from aiohttp import BasicAuth
from cryptography.fernet import Fernet
from io import StringIO
from pubsub import pub

if os.environ.get("LOCAL") != 'TRUE':
    import aiohttp
    import meshtastic.tcp_interface
    import meshtastic

load_dotenv()

#Import Config
from utils.config import API_URL, API_TIMEOUT, DEBUG, LORASERVICE_PATH, OFFLINE_FULL_LOAD_FILENAME, HOME_DIR, \
    TOPIC, TOPIC_PREFIX, MQTT_BROKER, MQTT_PORT, MQTT_TRANSPORT, MQTT_VERSION, MQTT_KEEPALIVE,   \
    LOG_FILENAME, MAX_LOG_SIZE, BACKUP_COUNT, BEACON_LOCATIONS, IDFACILITY, \
    MESHTASTIC_SERVER_NODE_ID

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

FILEPATH = f"{LORASERVICE_PATH}/data"

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

# Meshtastic Interface - Connect to meshtasticd daemon via TCP
mesh_interface = None
if os.environ.get("LOCAL") != 'TRUE':
    try:
        mesh_interface = meshtastic.tcp_interface.TCPInterface(hostname='localhost')
        logging.info(f'Connected to Meshtastic daemon at localhost:4403')
        logging.info(f'Server Node ID: {MESHTASTIC_SERVER_NODE_ID}')
    except Exception as e:
        logging.error(f'Failed to connect to Meshtastic daemon: {e}')
        exit(1)
else:
    logging.info('Bypassing Meshtastic Module (LOCAL mode)')

# Get MQTT credentials from secure storage with offline fallback
mqtt_username_result = get_secret('mqttUsername')
mqtt_password_result = get_secret('mqttPassword')

if not mqtt_username_result or not mqtt_password_result:
    logging.error("Failed to retrieve MQTT credentials - using defaults for testing only")
    mqtt_username = "IQRight"
    mqtt_password = "123456"
else:
    mqtt_username = mqtt_username_result["value"]
    mqtt_password = mqtt_password_result["value"]

mqtt_client = mqtt.Client(client_id="IQRight_Daemon", transport=MQTT_TRANSPORT, protocol=mqtt.MQTTv5)
mqtt_client.username_pw_set(mqtt_username, mqtt_password)

properties=Properties(PacketTypes.CONNECT)
properties.SessionExpiryInterval=30*60 # in seconds
mqtt_client.connect(MQTT_BROKER,
               port=MQTT_PORT,
               clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
               properties=properties,
               keepalive=MQTT_KEEPALIVE)
logging.info('Connected to MQTT Server')

# Start MQTT loop in background thread (non-blocking)
mqtt_client.loop_start()
logging.info('MQTT client loop started in background thread')

lastCommand = None
pending_responses = {}

# Thread pool for processing messages without blocking Meshtastic callbacks
message_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="MessageHandler")

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
        keyfilename = (f"{FILEPATH}/{keyfilename}") if keyfilename else None
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
            # Handle list of results (multi-packet protocol)
            if isinstance(payload, list):
                total_messages = len(payload)
                for idx, item in enumerate(payload, start=1):
                    time.sleep(0.3)  # Small delay between messages
                    if sendDataScanner(item, source_node, message_num=idx, total_messages=total_messages) == False:
                        logging.error(f'FAILED to send to Scanner ({idx}/{total_messages}): {json.dumps(item)}')
                    else:
                        sendObj = json.dumps(item)
                        logging.info(f'Sent packet {idx}/{total_messages}: {sendObj}')
                        hierarchyID = str(item.get("hierarchyID", '00'))
                        if publishMQTT(sendObj, hierarchyID):
                            logging.info(' Message Sent to MQTT')
                        else:
                            logging.error('MQTT ERROR')
            else:
                # Handle single command payload (1/1 message)
                time.sleep(0.3)
                if sendDataScanner(payload, source_node, message_num=1, total_messages=1) == False:
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

def sendDataScanner(payload: dict, destination_node: int, message_num: int = 1, total_messages: int = 1):
    """
    Send data back to scanner via Meshtastic with multi-packet protocol

    Message format: "name|grade_initial|teacher|msg_num/total_msgs"
    Example: "John Smith|5|Mrs Jane|1/3" means message 1 of 3

    CRITICAL LIMIT: 32 bytes max to avoid meshtasticd TCP buffer panic
    The "bytes size exceeded" panic occurs when meshtasticd re-encodes
    packets for TCP clients, even though over-the-air limit is 233 bytes.
    """
    try:
        if 'name' in payload:
            # Get first letter of grade
            grade_initial = getGrade(payload['hierarchyLevel1'])[:1]
            grade_teacher = payload['hierarchyLevel2']

            # AGGRESSIVE truncation to avoid TCP buffer panic in meshtasticd
            # Limit: 32 bytes total to stay well under internal buffer limits
            name_truncated = payload['name'][:15]  # Max 15 chars for name
            teacher_truncated = grade_teacher[:10]  # Max 10 chars for teacher

            # Build message: "Name|G|Teacher|1/2" format
            msg = f"{name_truncated}|{grade_initial}|{teacher_truncated}|{message_num}/{total_messages}"

            # Enforce STRICT 32-byte limit (meshtasticd TCP bug workaround)
            msg_bytes = msg.encode('utf-8')
            if len(msg_bytes) > 32:
                logging.warning(f"Message {len(msg_bytes)} bytes > 32, aggressive truncation")
                # Further reduce name/teacher to fit
                name_safe = payload['name'][:10]
                teacher_safe = grade_teacher[:6]
                msg = f"{name_safe}|{grade_initial}|{teacher_safe}|{message_num}/{total_messages}"

                # Absolute fallback - truncate at byte level
                msg_bytes = msg.encode('utf-8')
                if len(msg_bytes) > 32:
                    msg = msg_bytes[:30].decode('utf-8', errors='ignore')

        else:
            # Command acknowledgment
            msg = f"cmd|ack|{payload['command']}"
            print(msg)

        logging.debug(f'Sending to node {destination_node} ({message_num}/{total_messages}): {msg} (length: {len(msg)} chars, {len(msg.encode("utf-8"))} bytes)')

        # Send with acknowledgment using Meshtastic
        mesh_interface.sendText(
            text=msg,
            destinationId=destination_node,
            wantAck=True
        )

        logging.info(f'Packet {message_num}/{total_messages} sent to node {destination_node}')
        return True

    except Exception as e:
        logging.error(f"Failed to send packet {message_num}/{total_messages} to node {destination_node}: {e}")
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

def process_message_in_thread(message_text: str, source_node: int):
    """
    Process message in separate thread with its own event loop
    This prevents event loop conflicts with Meshtastic TCP interface
    """
    thread_id = threading.current_thread().name
    logging.debug(f"[{thread_id}] Processing message from {source_node}: {message_text}")

    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(handleInfo(message_text, source_node))
    finally:
        loop.close()

    logging.debug(f"[{thread_id}] Completed processing message from {source_node}")

def onReceive(packet, interface):
    """
    Callback for received Meshtastic messages
    IMPORTANT: This must return immediately to avoid blocking the Meshtastic event loop
    """
    try:
        # Check if this is a text message
        if 'decoded' in packet and 'text' in packet['decoded']:
            message_text = packet['decoded']['text']
            source_node = packet['from']

            logging.info(f"Received from node {source_node}: {message_text}")

            # Submit to thread pool - returns immediately
            message_executor.submit(process_message_in_thread, message_text, source_node)
            logging.debug(f"Submitted message from {source_node} to processing queue")

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
    # Test mode with thread pool
    message_executor.submit(process_message_in_thread, '102|123456789|1', 102)
else:
    logging.info("Starting Meshtastic server listener...")
    logging.info("Waiting for messages from scanners...")

# Keep the script running to receive messages
# MQTT runs in background thread via loop_start()
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    logging.info("Shutting down...")
    message_executor.shutdown(wait=True)
    if mesh_interface:
        mesh_interface.close()
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    logging.info("Shutdown complete")

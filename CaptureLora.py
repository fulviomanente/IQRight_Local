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
    PROJECT_ID, BEACON_LOCATIONS, IDFACILITY, \
    LORA_NODE_ID, LORA_FREQUENCY, LORA_TX_POWER, LORA_ENABLE_CA

# Import enhanced LoRa packet handler
from lora import LoRaTransceiver, LoRaPacket, PacketType, NodeType, MultiPartFlags, CollisionAvoidance
    

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


# Initialize enhanced LoRa transceiver (handles hardware setup internally)
transceiver = LoRaTransceiver(
    node_id=LORA_NODE_ID,
    node_type=NodeType.SERVER,
    frequency=LORA_FREQUENCY,
    tx_power=LORA_TX_POWER
)


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
        logging.debug(f'Attempting Student Local Lookup...')
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
    """
    Get student info from API or local database (whichever responds first)

    Strategy:
    1. Start both API and local lookups in parallel
    2. Wait for first result with 2-second timeout
    3. Prefer API result if it completes first and has data
    4. Fall back to local if API times out or returns None
    """
    api_task = asyncio.create_task(get_user_from_api(code))
    local_task = asyncio.create_task(get_user_local(beacon, code, distance, df))

    try:
        # Wait for the first task to complete, with overall 2-second timeout
        done, pending = await asyncio.wait(
            [api_task, local_task],
            timeout=2.0,
            return_when=asyncio.FIRST_COMPLETED
        )

        # Check if API completed first with valid data
        if api_task in done:
            api_result = await api_task
            if api_result:
                # API returned data - use it
                if not isinstance(api_result, list):
                    api_result = [api_result]
                for result in api_result:
                    result["source"] = "api"
                logging.debug("Using API results (completed first)")

                # Cancel local task if still running
                if local_task in pending:
                    local_task.cancel()

                return api_result

        # Check if local completed first or API returned None
        if local_task in done:
            local_result = await local_task
            if local_result:
                logging.debug("Using local results")

                # Cancel API task if still running
                if api_task in pending:
                    api_task.cancel()

                return local_result

        # If we get here, timeout occurred or both returned None
        # Wait for any pending tasks to complete
        if pending:
            logging.warning("Timeout reached, waiting for remaining tasks...")
            remaining_done, remaining_pending = await asyncio.wait(pending, timeout=0.5)

            # Check results from remaining tasks
            for task in remaining_done:
                result = await task
                if result:
                    if task == api_task:
                        if not isinstance(result, list):
                            result = [result]
                        for r in result:
                            r["source"] = "api"
                        logging.debug("Using API results (after timeout)")
                    else:
                        logging.debug("Using local results (after timeout)")
                    return result

        logging.warning("No results from API or local lookup")
        return None

    except asyncio.CancelledError:
        logging.warning("getInfo was cancelled")
        # Cancel both tasks
        api_task.cancel()
        local_task.cancel()
        return None
    except Exception as ex:
        logging.error(f'Error in getInfo: {ex}')
        # Cancel both tasks on error
        api_task.cancel()
        local_task.cancel()
        return None

async def handleInfo(strInfo: str, source_node: int, packet_type: PacketType):
    """
    Handle incoming info request from scanner

    Args:
        strInfo: Payload string from scanner (beacon|code|distance)
        source_node: Source node ID (scanner that sent request)
    """
    global lastCommand
    ret = False
    payload = None
    if len(strInfo) > 5:
        if packet_type == PacketType.CMD:
            command = strInfo.split('|')
            if command[2] != lastCommand:
                # Handle single command payload
                payload = {'command': command[2]}
                time.sleep(RFM9X_SEND_DELAY)
                if sendDataScanner(payload, source_node, packet_index=0, total_packets=0) == False:
                    logging.error(f'FAILED to send to Scanner: {json.dumps(payload)}')
                else:
                    sendObj = json.dumps(payload)
                    logging.info(sendObj)
                    if publishMQTT(sendObj):
                        logging.info(' Message Sent')
                    else:
                        logging.error('MQTT ERROR')
        elif packet_type == PacketType.DATA:
            #Handle Data Packets
            beacon, payload_code, distance = strInfo.split('|')
            sendObj = await getInfo(beacon, payload_code, distance, df)
            payload = sendObj if sendObj else None
            if payload:
                total_packets = len(payload)
                for idx, item in enumerate(payload, start=1):
                    time.sleep(RFM9X_SEND_DELAY)
                    if sendDataScanner(item, source_node, packet_index=idx, total_packets=total_packets) == False:
                        logging.error(f'FAILED to send to Scanner: {json.dumps(item)}')
                    else:
                        sendObj = json.dumps(item)
                        hierarchyID = str(item.get("hierarchyID", '00'))
                        if publishMQTT(sendObj, hierarchyID):
                            logging.debug('MQTT Message Sent')
                        else:
                            logging.error('MQTT ERROR')

    return True

def sendDataScanner(payload: dict, dest_node: int, packet_index: int = 0, total_packets: int = 0):
    """
    Send data to scanner using enhanced packet protocol

    Args:
        payload: Dictionary with student info or command
        dest_node: Destination scanner node ID
        packet_index: Index in multi-packet sequence (0 if single)
        total_packets: Total packets in sequence (0 if single)
    """
    try:
        # Build message payload
        if 'name' in payload:
            grade_initial = getGrade(payload['hierarchyLevel1'])[:1]
            # Send hierarchyID instead of teacher name to save bytes
            msg = f"{payload['name']}|{grade_initial}|{payload['hierarchyID']}"
        else:
            msg = f"cmd|ack|{payload['command']}"

        # Create packet using transceiver helper
        packet = transceiver.create_data_packet(
            dest_node=dest_node,
            payload=msg.encode('utf-8'),
            use_ack=True,
            multi_part_index=packet_index,
            multi_part_total=total_packets
        )

        # Send with collision avoidance if enabled
        if LORA_ENABLE_CA and transceiver.rfm9x:
            data = packet.serialize()
            success = CollisionAvoidance.send_with_ca(
                transceiver.rfm9x,
                data,
                max_retries=3,
                enable_rx_guard=True,
                enable_random_delay=True
            )
        else:
            success = transceiver.send_packet(packet, use_ack=True)

        if success:
            logging.info(f'Sent to scanner {dest_node}: {msg} [{packet_index}/{total_packets}]')
        else:
            logging.error(f'Failed to send to scanner {dest_node}: {msg}')

        return success

    except Exception as e:
        logging.error(f'Error in sendDataScanner: {e}')
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
        sendTopic = f'{Topic}{topicSufix}'
    else:
        sendTopic = CommandTopic
    ret = client.publish(sendTopic, payload)
    if ret[0] == 0:
        logging.debug(f'Message sent to Topic: sendTopic')
        logging.debug(f'Message ID {ret[1]}')
        return True
    else:
        logging.error(f'FAILED to sent to Topic: sendTopic. Status {ret[0]}, Error: {ret[1]}')
        return False

def beaconLocator(idBeacon: int):
    if idBeacon in beacon_locations_dict:
        location = beacon_locations_dict[idBeacon]["location"]
        return location
    else:
        return ''

def handle_hello_packet(packet: LoRaPacket):
    """
    Handle HELLO handshake from scanner or repeater

    When a scanner reboots, it sends HELLO to reset sequence tracking.
    Server responds with HELLO_ACK to confirm synchronization.

    Args:
        packet: HELLO packet from scanner
    """
    try:
        logging.info("=" * 60)
        logging.info("HELLO PACKET RECEIVED!")
        logging.info(f"Full packet: {packet}")

        source_node = packet.source_node
        payload_str = packet.payload.decode('utf-8')
        logging.info(f"Payload string: {payload_str}")

        parts = payload_str.split('|')
        logging.info(f"Payload parts: {parts}")

        if parts[0] != "HELLO" or len(parts) < 3:
            logging.error(f"Invalid HELLO packet format: {payload_str}")
            logging.error(f"Expected: HELLO|seq|node_type, got {len(parts)} parts")
            return

        scanner_seq = int(parts[1])
        node_type = parts[2]

        logging.info(f"✓ HELLO from {node_type} node {source_node}, seq={scanner_seq}")

        # Clear sequence tracking for this node (reset duplicate detection)
        cache_size_before = len(transceiver.seen_packets)
        transceiver.seen_packets = {
            (src, seq) for src, seq in transceiver.seen_packets
            if src != source_node
        }
        cache_size_after = len(transceiver.seen_packets)
        logging.info(f"✓ Cleared sequence cache for node {source_node} (removed {cache_size_before - cache_size_after} entries)")

        # Send HELLO_ACK response
        logging.info(f"Creating HELLO_ACK for node {source_node}...")
        ack_packet = transceiver.create_hello_ack_packet(source_node)
        logging.info(f"HELLO_ACK packet created: {ack_packet}")

        logging.info("Sending HELLO_ACK...")
        success = transceiver.send_packet(ack_packet, use_ack=False)

        if success:
            logging.info(f"✓ HELLO_ACK sent successfully to node {source_node}")
        else:
            logging.error(f"✗ Failed to send HELLO_ACK to node {source_node}")

        logging.info("=" * 60)

    except Exception as e:
        logging.error(f"✗ Error handling HELLO packet: {e}", exc_info=True)
        logging.error("=" * 60)

# Main Loop
if os.getenv("LOCAL") == 'TRUE':
    asyncio.run(handleInfo('102|123456789|1', 102))
else:
    while True:
        # Receive packet using enhanced packet handler
        packet = transceiver.receive_packet(timeout=RMF9X_POOLING)

        if packet:
            try:
                # Check for HELLO packet first
                if packet.packet_type == PacketType.HELLO:
                    handle_hello_packet(packet)
                    continue

                # Extract payload and source node from packet
                packet_text = packet.payload.decode('utf-8')
                source_node = packet.source_node

                if DEBUG:
                    logging.debug(f'{packet} Received')
                    logging.debug(f'{packet_text} Converted to String')
                    logging.debug('RX: ')
                    logging.debug(packet_text)

                # Process the packet
                asyncio.run(handleInfo(packet_text, source_node, packet.packet_type))

            except UnicodeDecodeError as e:
                logging.error(f'{packet.payload}: Invalid UTF-8 String')
                logging.error(f'{e.__str__()}')
            except Exception as e:
                logging.error(f'Error processing packet: {e}')
                logging.error(f'{e.__str__()}')
        else:
            if DEBUG:
                logging.debug('No packet received (timeout)')

        time.sleep(0.1)  # Brief sleep to prevent CPU spinning

client.loop_forever();

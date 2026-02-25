 # Import Python System Libraries
import time
import logging
import logging.handlers
import os
import json
from datetime import datetime
import asyncio
from utils.api_client import get_secret
import aiohttp
from dotenv import load_dotenv
from aiohttp import BasicAuth

load_dotenv()

#Import Config
from utils.config import API_URL, API_TIMEOUT, DEBUG, HOME_DIR, \
    TOPIC, TOPIC_PREFIX, MQTT_BROKER, MQTT_PORT,  MQTT_TRANSPORT,  MQTT_KEEPALIVE,   \
    LOG_FILENAME, MAX_LOG_SIZE, BACKUP_COUNT, RFM9X_SEND_DELAY, RMF9X_POOLING, BEACON_LOCATIONS, IDFACILITY, \
    LORA_NODE_ID, LORA_FREQUENCY, LORA_TX_POWER, LORA_ENABLE_CA, \
    RESTRICTED_GRADES, UNRESTRICTED_DATES, \
    API_ENABLED, LOOKUP_TIMEOUT
from utils.offline_data import OfflineData

# Import enhanced LoRa packet handler
from lora import LoRaTransceiver, LoRaPacket, PacketType, NodeType, CollisionAvoidance
    

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

COMMAND_TOPIC = "IQRSend"

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
logging.info(f"Lookup mode: {'API + Local' if API_ENABLED else 'LOCAL ONLY'} | Timeout: {LOOKUP_TIMEOUT}s | API Timeout: {API_TIMEOUT}s")


def on_mqtt_message(client, userdata, message):
    """Handle incoming MQTT messages (web handshake requests)."""
    try:
        payload = json.loads(str(message.payload, 'UTF-8'))
        if payload.get('type') == 'web_hello':
            class_code = payload.get('classCode')
            user_name = payload.get('userName', 'unknown')
            logging.info(f"[MQTT-HANDSHAKE] web_hello from {user_name}, classCode={class_code}")

            ack_payload = json.dumps({
                "type": "web_hello_ack",
                "classCode": class_code,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            topic = f"{Topic}{class_code}"
            ret = client.publish(topic, ack_payload, qos=1)
            if ret[0] == 0:
                logging.info(f"[MQTT-HANDSHAKE] web_hello_ack sent to {topic}")
            else:
                logging.error(f"[MQTT-HANDSHAKE] FAILED to send web_hello_ack to {topic}")
    except Exception as e:
        logging.error(f"[MQTT-HANDSHAKE] Error handling message: {e}", exc_info=True)


client.on_message = on_mqtt_message
client.subscribe("IQRHandshake", qos=1)
client.loop_start()
logging.info("[MQTT] Subscribed to IQRHandshake, loop started")

# Per-scanner response cache for deduplication
# Key: (source_node, code) → Value: list of result dicts (the payload_to_scanner)
# Prevents double-publish to MQTT when scanner retries after timeout
scanner_response_cache = {}

offlineData = OfflineData()
offlineData.start_scheduled_refresh()

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
    elif strGrade[0:1] == 'K': # Assuming 'K' for Kindergarten
        return 'Kind'
    else:
        return 'N/A'

def is_grade_restricted(grade_raw: str) -> bool:
    """Check if a grade should be filtered out today based on RESTRICTED_GRADES config."""
    if not RESTRICTED_GRADES:
        return False
    today = datetime.now().strftime('%Y-%m-%d')
    if today in UNRESTRICTED_DATES:
        return False
    grade = getGrade(grade_raw)
    return grade in RESTRICTED_GRADES

def filter_restricted_grades(results: list) -> list:
    """Remove restricted grade students from results. Returns filtered list."""
    if not RESTRICTED_GRADES:
        return results
    today = datetime.now().strftime('%Y-%m-%d')
    if today in UNRESTRICTED_DATES:
        logging.info(f"[GRADE-FILTER] Today ({today}) is an unrestricted date - allowing all grades")
        return results

    filtered = []
    removed = []
    for item in results:
        grade_raw = item.get('hierarchyLevel1', '')
        if is_grade_restricted(grade_raw):
            removed.append(f"{item.get('name', '?')} ({getGrade(grade_raw)})")
        else:
            filtered.append(item)

    if removed:
        logging.info(f"[GRADE-FILTER] Filtered out {len(removed)} restricted student(s): {', '.join(removed)}")

    return filtered

async def get_user_from_api(code):
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
                

async def get_user_local(beacon, code, distance):
    if not code:  # Return early if code is missing
        logging.error(f'Empty string sent for conversion into MQTT Object')
        return None

    try:
        logging.debug(f'Attempting Student Local Lookup...')
        df = offlineData.getAppUsers()
        filtered_df = df[df['DeviceID'] == code]
        matches = filtered_df.drop_duplicates(subset=['ChildName'])
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
                    "classCode": row['ClassCode'],
                    "source": "local"
                }
                results.append(result)
            return results
    except Exception as e:
        logging.error(f'Error converting local data: {e}')
        return None


async def getInfo(beacon, code, distance):
    """
    Get student info from API and/or local database.

    Controlled by config:
        API_ENABLED=TRUE  → Race API + local in parallel (original behavior)
        API_ENABLED=FALSE → Local-only lookup (fastest, no network dependency)
        LOOKUP_TIMEOUT    → Overall timeout in seconds (default 2.0)
    """
    # Local-only mode — skip API entirely
    if not API_ENABLED:
        logging.debug("API disabled - local-only lookup")
        return await get_user_local(beacon, code, distance)

    # Dual mode — race API and local in parallel
    api_task = asyncio.create_task(get_user_from_api(code))
    local_task = asyncio.create_task(get_user_local(beacon, code, distance))

    try:
        done, pending = await asyncio.wait(
            [api_task, local_task],
            timeout=LOOKUP_TIMEOUT,
            return_when=asyncio.FIRST_COMPLETED
        )

        # Check if API completed first with valid data
        if api_task in done:
            api_result = await api_task
            if api_result:
                if not isinstance(api_result, list):
                    api_result = [api_result]
                for result in api_result:
                    result["source"] = "api"
                logging.debug("Using API results (completed first)")
                if local_task in pending:
                    local_task.cancel()
                return api_result

        # Check if local completed first or API returned None
        if local_task in done:
            local_result = await local_task
            if local_result:
                logging.debug("Using local results")
                if api_task in pending:
                    api_task.cancel()
                return local_result

        # Timeout — wait a bit more for any pending tasks
        if pending:
            logging.warning(f"Lookup timeout ({LOOKUP_TIMEOUT}s), waiting for remaining tasks...")
            remaining_done, remaining_pending = await asyncio.wait(pending, timeout=0.5)

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

            # Cancel anything still running
            for task in remaining_pending:
                task.cancel()

        logging.warning("No results from API or local lookup")
        return None

    except asyncio.CancelledError:
        logging.warning("getInfo was cancelled")
        api_task.cancel()
        local_task.cancel()
        return None
    except Exception as ex:
        logging.error(f'Error in getInfo: {ex}')
        api_task.cancel()
        local_task.cancel()
        return None

async def handleInfo(packet_payload_str: str, source_node: int, packet_type: PacketType):
    """
    Handle incoming info request from scanner

    Args:
        packet_payload_str: Payload string from scanner
        source_node: Source node ID (scanner that sent request)
        packet_type: Type of the LoRa packet
    """
    
    if packet_type == PacketType.CMD:
        # Command packet format: "command_name" (e.g., "break", "release", "undo", "cleanup")
        command = packet_payload_str.split("|")
        logging.info(f"Received command '{command[2]}' from scanner {source_node}")
        
        # Clear dedup cache for this scanner on cleanup (fresh session)
        cmd_name = command[2]
        if cmd_name == 'cleanup':
            cleared = {k for k in scanner_response_cache if k[0] == source_node}
            for k in cleared:
                del scanner_response_cache[k]
            logging.info(f"[DEDUP] Cleared cache for scanner {source_node} on cleanup ({len(cleared)} entries)")

        payload_to_scanner = {'command': cmd_name}
        if sendDataScanner(payload_to_scanner, source_node, packet_type=PacketType.CMD) == False:
            logging.error(f'FAILED to send command ACK to Scanner: {json.dumps(payload_to_scanner)}')
        else:
            sendObj = json.dumps(payload_to_scanner)
            logging.info(f"Command ACK sent to scanner {source_node}: {sendObj}")
            if publishMQTT(sendObj, topicSufix="command"): # Use command as suffix for MQTT topic
                logging.info(' Command ACK Message Sent to MQTT')
            else:
                logging.error('MQTT ERROR publishing command ACK')

    elif packet_type == PacketType.DATA:
        # Data packet format: "beacon|code|distance"
        parts = packet_payload_str.split('|')
        if len(parts) != 3:
            logging.error(f"Invalid DATA packet format from node {source_node}: {packet_payload_str}")
            return

        beacon, payload_code, distance = parts
        logging.info(f"Received data from scanner {source_node}: Beacon={beacon}, Code={payload_code}, Distance={distance}")

        # Check dedup cache — if scanner is retrying after timeout, re-send cached response without MQTT
        cache_key = (source_node, payload_code)
        is_duplicate = cache_key in scanner_response_cache

        if is_duplicate:
            payload_to_scanner = scanner_response_cache[cache_key]
            logging.warning(f"[DEDUP] Duplicate code {payload_code} from scanner {source_node} - re-sending cached response, skipping MQTT")
        else:
            sendObj = await getInfo(beacon, payload_code, distance)
            if sendObj:
                # Filter restricted grades (7th/8th by default, unless unrestricted date)
                original_count = len(sendObj)
                sendObj = filter_restricted_grades(sendObj)
                if not sendObj and original_count > 0:
                    # All students were restricted grades — send RESTRICTED response
                    logging.info(f"[GRADE-FILTER] All {original_count} student(s) for code {payload_code} are restricted grades")
                    restricted_msg = f"RESTRICTED|{payload_code}|00"
                    restricted_packet = transceiver.create_data_packet(
                        dest_node=source_node,
                        payload=restricted_msg.encode('utf-8'),
                        use_ack=True
                    )
                    time.sleep(RFM9X_SEND_DELAY)
                    if LORA_ENABLE_CA and transceiver.rfm9x:
                        data = restricted_packet.serialize()
                        success = CollisionAvoidance.send_with_ca(
                            transceiver.rfm9x, data,
                            max_retries=3, enable_rx_guard=True, enable_random_delay=True
                        )
                    else:
                        success = transceiver.send_packet(restricted_packet, use_ack=True)
                    if success:
                        logging.info(f"RESTRICTED response sent to scanner {source_node} for code {payload_code}")
                    else:
                        logging.error(f"FAILED to send RESTRICTED response to scanner {source_node}")
                    return
            payload_to_scanner = sendObj if sendObj else None

        if payload_to_scanner:
            # Cache the response for future dedup
            if not is_duplicate:
                scanner_response_cache[cache_key] = payload_to_scanner

            total_packets = len(payload_to_scanner)
            for idx, item in enumerate(payload_to_scanner, start=1):
                time.sleep(RFM9X_SEND_DELAY)
                if sendDataScanner(item, source_node, packet_type=PacketType.DATA, packet_index=idx, total_packets=total_packets) == False:
                    logging.error(f'FAILED to send data to Scanner: {json.dumps(item)}')
                else:
                    if not is_duplicate:
                        sendObj_json = json.dumps(item)
                        hierarchyID = str(item.get("hierarchyID", '00'))
                        if publishMQTT(sendObj_json, hierarchyID):
                            logging.debug('MQTT Data Message Sent')
                        else:
                            logging.error('MQTT ERROR publishing data')
                    else:
                        logging.info(f"[DEDUP] Skipped MQTT publish for duplicate {payload_code}")
        else:
            logging.warning(f"No data found for code {payload_code} from scanner {source_node}. Sending NOT_FOUND response.")
            # Send NOT_FOUND response so scanner doesn't timeout waiting
            not_found_msg = f"NOT_FOUND|{payload_code}|00"
            not_found_packet = transceiver.create_data_packet(
                dest_node=source_node,
                payload=not_found_msg.encode('utf-8'),
                use_ack=True
            )
            time.sleep(RFM9X_SEND_DELAY)
            if LORA_ENABLE_CA and transceiver.rfm9x:
                data = not_found_packet.serialize()
                success = CollisionAvoidance.send_with_ca(
                    transceiver.rfm9x, data,
                    max_retries=3, enable_rx_guard=True, enable_random_delay=True
                )
            else:
                success = transceiver.send_packet(not_found_packet, use_ack=True)
            if success:
                logging.info(f"NOT_FOUND response sent to scanner {source_node} for code {payload_code}")
            else:
                logging.error(f"FAILED to send NOT_FOUND response to scanner {source_node} for code {payload_code}")
    else:
        logging.warning(f"Unhandled packet type {packet_type} from node {source_node}")


def sendDataScanner(payload: dict, dest_node: int, packet_type: PacketType, packet_index: int = 0, total_packets: int = 0):
    """
    Send data or command to scanner using enhanced packet protocol

    Args:
        payload: Dictionary with student info or command
        dest_node: Destination scanner node ID
        packet_type: Type of packet to send (DATA or CMD)
        packet_index: Index in multi-packet sequence (0 if single)
        total_packets: Total packets in sequence (0 if single)
    """
    try:
        msg = ""
        if packet_type == PacketType.DATA:
            if 'name' in payload:
                # Send name and classCode only — scanner displays classCode directly (e.g., "4W")
                msg = f"{payload['name']}|{payload['classCode']}"

                # Create packet using transceiver helper
                packet = transceiver.create_data_packet(
                    dest_node=dest_node,
                    payload=msg.encode('utf-8'),
                    use_ack=True,
                    multi_part_index=packet_index,
                    multi_part_total=total_packets
                )

            else:
                logging.error(f"Invalid payload for DATA packet: {payload}")
                return False
        elif packet_type == PacketType.CMD:
            if 'command' in payload:
                msg = payload['command'] # Command is the payload itself
                # Create packet using transceiver helper
                packet = transceiver.create_cmd_packet(dest_node=dest_node,command=msg)
            else:
                logging.error(f"Invalid payload for CMD packet: {payload}")
                return False
        else:
            logging.error(f"Unsupported packet type for sending: {packet_type}")
            return False



        # CMD ACKs send directly (like HELLO_ACK) — scanner is already listening
        # DATA packets use collision avoidance for multi-packet spacing
        if packet_type == PacketType.CMD:
            success = transceiver.send_packet(packet, use_ack=False)
        elif LORA_ENABLE_CA and transceiver.rfm9x:
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
            logging.info(f'Sent {packet_type.name} to scanner {dest_node}: {msg} [{packet_index}/{total_packets}]')
        else:
            logging.error(f'Failed to send {packet_type.name} to scanner {dest_node}: {msg}')

        return success

    except Exception as e:
        logging.error(f'Error in sendDataScanner: {e}')
        return False

def publishMQTT(payload: str, topicSufix: str = None):
    count = 5
    while count > 0:
        if sendMessageMQTT(payload, topicSufix):
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
    logging.info(f"[MQTT-TX] Sending to MQTT: {payload}")
    if topicPrefix and topicSufix:
        if topicSufix=="command":
            sendTopic = COMMAND_TOPIC
        else:
            sendTopic = f'{Topic}{topicSufix}'
    else: # If no topic prefix or suffix, use COMMAND_TOPIC for commands, or default Topic for data
        sendTopic = Topic

    # Use QoS 1 for reliable delivery (at least once)
    ret = client.publish(sendTopic, payload, qos=1)
    if ret[0] == 0:
        logging.info(f'[MQTT-TX] SUCCESS: Topic={sendTopic}, MsgID={ret[1]}, QoS=1')
        return True
    else:
        logging.error(f'[MQTT-TX] FAILED: Topic={sendTopic}, Status={ret[0]}, Error={ret[1]}')
        return False

def beaconLocator(idBeacon):
    try:
        idBeacon = int(idBeacon)
    except (ValueError, TypeError):
        return ''
    if idBeacon in BEACON_LOCATIONS:
        return BEACON_LOCATIONS[idBeacon]["location"]
    return ''

# Setup device status logger (separate file for device status tracking)
device_status_logger = logging.getLogger('device_status')
device_status_logger.setLevel(logging.INFO)
device_status_handler = logging.handlers.RotatingFileHandler(
    f'{HOME_DIR}/log/device_status.log',
    maxBytes=MAX_LOG_SIZE,
    backupCount=BACKUP_COUNT
)
device_status_formatter = logging.Formatter('%(asctime)s - %(message)s')
device_status_handler.setFormatter(device_status_formatter)
device_status_logger.addHandler(device_status_handler)
device_status_logger.propagate = False  # Don't send to root logger


def handle_status_packet(packet: LoRaPacket):
    """
    Handle STATUS packet from repeater (device health monitoring)

    PiSugar 3 sends periodic status updates via I2C.
    Format: "battery|charging|voltage|temperature|model[|event]"
    Example: "85.5|true|3.95|25|PiSugar3"
    With event: "85.5|true|3.95|25|PiSugar3|STARTUP"

    Args:
        packet: STATUS packet from repeater
    """
    try:
        source_node = packet.source_node
        sender_node = packet.sender_node
        payload_str = packet.payload.decode('utf-8')

        # Parse STATUS payload
        parts = payload_str.split('|')

        if len(parts) >= 5:
            battery = parts[0]
            charging = parts[1]
            voltage = parts[2]
            temperature = parts[3]
            model = parts[4]
            event = parts[5] if len(parts) >= 6 else None

            # Build log message
            event_label = f" [{event}]" if event else ""
            status_msg = (
                f"Node {source_node}{event_label} | "
                f"Battery: {battery}% | "
                f"Voltage: {voltage}V | "
                f"Charging: {charging} | "
                f"Temp: {temperature}°C | "
                f"Model: {model}"
            )

            device_status_logger.info(status_msg)

            # Main log — highlight startup/shutdown events
            if event == "STARTUP":
                logging.info(f">>> REPEATER {source_node} STARTED - Battery={battery}%, Voltage={voltage}V, Charging={charging}")
            elif event == "SHUTDOWN":
                logging.info(f"<<< REPEATER {source_node} SHUTTING DOWN - Battery={battery}%, Voltage={voltage}V, Charging={charging}")
            else:
                logging.info(f"STATUS from Node {source_node}: Battery={battery}%, Voltage={voltage}V, Charging={charging}")

        else:
            logging.warning(f"Invalid STATUS packet format from node {source_node}: {payload_str}")

    except Exception as e:
        logging.error(f"Error handling STATUS packet: {e}", exc_info=True)


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

        logging.info(f"HELLO from {node_type} node {source_node}, seq={scanner_seq}")

        # Clear response dedup cache for this node (scanner rebooted)
        cleared = {k for k in scanner_response_cache if k[0] == source_node}
        for k in cleared:
            del scanner_response_cache[k]
        if cleared:
            logging.info(f"[DEDUP] Cleared cache for node {source_node} on HELLO ({len(cleared)} entries)")

        # Clear sequence tracking for this node (reset duplicate detection)
        cache_size_before = len(transceiver.seen_packets)
        transceiver.seen_packets = {
            (src, seq) for src, seq in transceiver.seen_packets
            if src != source_node
        }
        cache_size_after = len(transceiver.seen_packets)
        logging.info(f"Cleared sequence cache for node {source_node} (removed {cache_size_before - cache_size_after} entries)")

        # Send HELLO_ACK response
        logging.info(f"Creating HELLO_ACK for node {source_node}...")
        ack_packet = transceiver.create_hello_ack_packet(source_node)
        logging.info(f"HELLO_ACK packet created: {ack_packet}")

        logging.info("Sending HELLO_ACK...")
        success = transceiver.send_packet(ack_packet, use_ack=False)

        if success:
            logging.info(f"HELLO_ACK sent successfully to node {source_node}")
        else:
            logging.error(f"Failed to send HELLO_ACK to node {source_node}")

        logging.info("=" * 60)

    except Exception as e:
        logging.error(f"Error handling HELLO packet: {e}", exc_info=True)
        logging.error("=" * 60)

async def main_loop_async():
    """Main asynchronous loop for receiving and processing LoRa packets."""

    # Adaptive logging state:
    #   IDLE       - Before any HELLO handshake; log timeouts every 5 min
    #   ACTIVE     - After HELLO received; log every timeout for close monitoring
    #   WIND_DOWN  - 15 min with no valid packets; back to every 5 min
    IDLE_LOG_INTERVAL = 300        # 5 minutes in seconds
    WIND_DOWN_THRESHOLD = 900      # 15 minutes in seconds

    is_active = False
    last_valid_packet_time = None
    last_timeout_log_time = time.time()

    logging.info("Server started in IDLE mode - logging timeouts every 5 minutes until HELLO received")

    while True:
        # Receive packet using enhanced packet handler
        packet = transceiver.receive_packet(timeout=RMF9X_POOLING)

        if packet:
            try:
                # Check for HELLO packet first
                if packet.packet_type == PacketType.HELLO:
                    if not is_active:
                        is_active = True
                        logging.info("=== SWITCHING TO ACTIVE MODE - monitoring all packets ===")
                    last_valid_packet_time = time.time()
                    handle_hello_packet(packet)
                    continue

                # Check for STATUS packet (device health monitoring)
                if packet.packet_type == PacketType.STATUS:
                    last_valid_packet_time = time.time()
                    handle_status_packet(packet)
                    continue

                # Extract payload and source node from packet
                packet_text = packet.payload.decode('utf-8')
                source_node = packet.source_node
                last_valid_packet_time = time.time()

                if DEBUG:
                    logging.debug(f'{packet} Received')
                    logging.debug(f'{packet_text} Converted to String')
                    logging.debug('RX: ')
                    logging.debug(packet_text)

                # Process the packet
                await handleInfo(packet_text, source_node, packet.packet_type)

            except UnicodeDecodeError as e:
                logging.error(f'{packet.payload}: Invalid UTF-8 String')
                logging.error(f'{e.__str__()}')
            except Exception as e:
                logging.error(f'Error processing packet: {e}')
                logging.error(f'{e.__str__()}')
        else:
            now = time.time()

            # Check if active mode should wind down (15 min no valid packets)
            if is_active and last_valid_packet_time and (now - last_valid_packet_time) >= WIND_DOWN_THRESHOLD:
                is_active = False
                logging.info(f"=== SWITCHING TO IDLE MODE - no valid packets for {WIND_DOWN_THRESHOLD // 60} minutes ===")

            # In ACTIVE mode: log every timeout
            if is_active:
                if DEBUG:
                    logging.debug('No packet received (timeout)')
            # In IDLE/WIND_DOWN mode: log only every 5 minutes
            else:
                if (now - last_timeout_log_time) >= IDLE_LOG_INTERVAL:
                    last_timeout_log_time = now
                    logging.info('No packet received - server idle (next check in 5 min)')

        await asyncio.sleep(0.1)  # Brief sleep to prevent CPU spinning

# Main Loop
if os.getenv("LOCAL") == 'TRUE':
    # In LOCAL mode, we might want to simulate a packet or run a test
    # For now, just log and exit as there's no hardware to listen on.
    logging.info("Running in LOCAL mode. No LoRa hardware detected. Exiting after test call.")
    asyncio.run(handleInfo('102|123456789|1', 102, PacketType.DATA)) # Simulate a data packet
else:
    try:
        asyncio.run(main_loop_async())
    except KeyboardInterrupt:
        logging.info("Server shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()
        logging.info("MQTT client disconnected.")

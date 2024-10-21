# Import Python System Libraries
import time
import logging
import logging.handlers
import os
import json
from datetime import datetime
import pandas as pd

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

TOPIC = f'IQSend'

homeDir = os.environ['HOME']

df = pd.read_csv('/etc/iqright/LoraService/full_load.csv',
                 dtype={'ChildID': int, 'IDUser': int, 'FirstName': str, 'LastName': str, 'AppIDApprovalStatus': int \
                     , 'AppApprovalStatus': str, 'DeviceID': str, 'Phone': str, 'ChildName': str, 'ExternalNumber': str \
                     , 'HierarchyLevel1': str, 'HierarchyLevel1Type': str, 'HierarchyLevel1Desc': str \
                     , 'HierarchyLevel2': str, 'HierarchyLevel2Type': str, 'HierarchyLevel2Desc': str \
                     , 'StartDate': str, 'ExpireDate': str, 'IDApprovalStatus': int, 'ApprovalStatus': str
                     , 'MainContact': int, 'Relationship': str})


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

def getInfo(beacon, code, distance):
    global df
    if code:
        try:
            logging.debug(f'Student Lookup')
            name = df.loc[df['ExternalNumber'] == code]
            if name.empty:
                logging.debug(f"Couldn't find Code: {code}")
                return None
            else:
                result = {"name": name['ChildName'].item(), "level1": name['HierarchyLevel1'].item(), "level2": name['HierarchyLevel2'].item(),
                    "node": beacon, "externalID": code, "distance": abs(int(distance)), "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "externalNumber": name['ExternalNumber'].item()}
                return result
            #return {"node": beacon, "phoneID": code, "distance": abs(int(distance)), "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        except Exception as e:
            logging.error(f'Error converting string {beacon}|{code}|{distance} into MQTT Object')
    else:
        logging.error(f'Empty string sent for conversion into MQTT Object')
    return None

def handleInfo(strInfo: str):
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
            sendObj = getInfo(beacon, payload, distance)
            payload = sendObj if sendObj else None
        if payload:
            ret = True
    return ret, payload

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
        if sendMessageMQTT(payload):
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

def sendMessageMQTT(payload: str):
    logging.info(f"Sending {sendObj} to MQTT")
    ret = client.publish(TOPIC, sendObj)
    if ret[0] == 0:
        logging.debug('Message sent to Topic: IQSend')
        logging.debug(f'Message ID {ret[1]}')
        return True
    else:
        logging.error(ret[0])
        logging.error(ret[1])
        logging.error('FAILED to sent to Topic: IQSend')
        return False
    
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
                    result, payload = handleInfo(packet_text)
                if result:
                    #IF ALL DATA COULD BE PARSED AND IDENTIFIED, SEND TO THE SCANNER
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
                            
                else:
                    logging.error('No response received from MQ Topic: IQSend or Empty Message received from Lora')
            else:
                if debug:
                    logging.debug('Empty Package Received')
            time.sleep(0.9)


client.loop_forever();
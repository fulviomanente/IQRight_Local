import os
import tkinter as tk
from tkinter import ttk
from datetime import datetime
import time
import paho.mqtt.client as mqtt
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes
from tksheet import Sheet
#import pyttsx3
from gtts import gTTS
from io import BytesIO
from pydub import AudioSegment
from pydub.playback import play
import pandas as pd
import json
from os.path import exists
import logging
import logging.handlers

#LOGGING Setup
log_filename = "IQRight_FE.debug"
max_log_size = 20 * 1024 * 1024 #20Mb
backup_count = 10
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
debug = True
handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=max_log_size, backupCount=backup_count)

handler.setFormatter(log_formatter)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)

lastCommand = None

df = pd.read_csv('/etc/iqright/LoraService/full_load.iqr',
                 dtype={'ChildID': int, 'IDUser': int, 'FirstName': str, 'LastName': str, 'AppIDApprovalStatus': int \
                     , 'AppApprovalStatus': str, 'DeviceID': str, 'Phone': str, 'ChildName': str, 'ExternalNumber': str \
                     , 'HierarchyLevel1': str, 'HierarchyLevel1Type': str, 'HierarchyLevel1Desc': str \
                     , 'HierarchyLevel2': str, 'HierarchyLevel2Type': str, 'HierarchyLevel2Desc': str \
                     , 'StartDate': str, 'ExpireDate': str, 'IDApprovalStatus': int, 'ApprovalStatus': str
                     , 'MainContact': int, 'Relationship': str})


class FlashableLabel(tk.Label):
    def flash(self, count):
        bg = self.cget('background')
        fg = self.cget('foreground')
        self.configure(background=fg, foreground=bg)
        count += 1
        if (count < 5):
            self.after(1000, self.flash, count)


def connect():
    broker = '127.0.0.1'  # eg. choosen-name-xxxx.cedalo.cloud
    myport = 1883
    client.connect(broker,
                   port=myport,
                   keepalive=60);


version = '5'  # or '3'
mytransport = 'tcp'  # 'websockets' # or 'tcp'

# Create the main window
root = tk.Tk()
root.title("Centerton Gamble Elementary")
root.configure(bg='white')

client = mqtt.Client(client_id="IQRight_Main", transport=mytransport, protocol=mqtt.MQTTv5)
client.username_pw_set("IQRight", "123456")

broker = 'localhost'  # eg. choosen-name-xxxx.cedalo.cloud
myport = 1883
properties = Properties(PacketTypes.CONNECT)
properties.SessionExpiryInterval = 30 * 60  # in seconds

#engine = pyttsx3.init()

#df = pd.read_csv('full_load.iqr',
#                 dtype={'ChildID': int, 'IDUser': int, 'FirstName': str, 'LastName': str, 'AppIDApprovalStatus': int \
#                     , 'AppApprovalStatus': str, 'DeviceID': str, 'Phone': str, 'ChildName': str, 'ExternalNumber': str \
#                     , 'HierarchyLevel1': str, 'HierarchyLevel1Type': str, 'HierarchyLevel1Desc': str \
#                     , 'HierarchyLevel2': str, 'HierarchyLevel2Type': str, 'HierarchyLevel2Desc': str \
#                     , 'StartDate': str, 'ExpireDate': str, 'IDApprovalStatus': int, 'ApprovalStatus': str
#                     , 'MainContact': int, 'Relationship': str})

memoryData = {"list1": []}
currList = 1
gridList = 1
loadGrid = 1

# node = sx126x.sx126x(serial_num = "/dev/ttyS0",freq=868,addr=0,power=22,rssi=True,air_speed=2400,relay=False)

def update_label():
    # Update the label text
    label.config(text=f"{datetime.now().strftime('%H:%M:%S')}    ")
    # Schedule the next update in 100ms
    root.after(1000, update_label)

def playSoundList(listObj, currGrid, fillGrid: bool = False):

    for jsonObj in listObj:
        externalNumber = jsonObj['externalNumber']
        label_call.config(text=f"{jsonObj['name']} - {jsonObj['level1']}")
        currGrid.insert_row([jsonObj['name'], jsonObj['level1'], jsonObj['level2']], redraw=True)
        #rate = engine.getProperty('rate')
        #engine.setProperty('rate', 130)
        if exists(f'./Sound/{externalNumber}.mp3') == False:
            logging.info(f'Missing Audio File - {externalNumber}.mp3')
            logging.info(f'Generating from Google')
            tts = gTTS(f"{jsonObj['level1']}, {jsonObj['name']}", lang='en')
            tts.save(f'./Sound/{externalNumber}.mp3')
        else:
            if os.environ.get("MAC", None) != None:
                print(f'Calling {externalNumber}')
            else:
                song = AudioSegment.from_file(f'./Sound/{externalNumber}.mp3', format="mp3")
                play(song)
            label_call.flash(0)
        if fillGrid: #IF FILLING THE WHOLE GRID, SLEEP 2 SECONDS BEFORE PLAYING THE NEXT ONE
            time.sleep(2)
        
def on_messageScreen(client, userdata, message, tmp=None):
    global currGrid
    global memoryData
    global currList
    global debug
    global gridList
    global loadGrid
    global lastCommand
    print('Message Received')
    print(str(message.payload, 'UTF-8'))
    if debug:
        logging.debug('Message Received')
        logging.debug(str(message.payload, 'UTF-8'))
        bleMsg = str(message.payload, 'UTF-8')
        jsonObj = loadJson(str(message.payload, 'UTF-8'))
        if isinstance(jsonObj, dict):
            if 'command' in jsonObj:
                if lastCommand != jsonObj['command']:
                    lastCommand = jsonObj['command']
                    if jsonObj['command'] == 'break':
                        if gridList == 1:
                            currGrid = sheet2
                            gridList = 2
                        currList += 1
                        memoryData[f"list{currList}"] = []
                        print(f'currGrid = sheet2 \ currList = {currList} \ griList = {gridList}')
                    elif jsonObj['command'] == 'release':
                        #move grid 2 to grid 1
                        sheet1.column_width(0, 400)
                        sheet1.column_width(1, 250)
                        sheet1.column_width(2, 250)
                        sheet1.set_sheet_data(sheet2.get_sheet_data(), redraw=True, reset_col_positions = False)
                        #empty grid 2
                        sheet2.delete_rows([ x for x in range(0, currGrid.get_total_rows())], redraw=True)
                        loadGrid += 1
                        secondGrid = loadGrid + 1
                        if currList >= secondGrid:
                            sheet2.set_sheet_data([[x['name'], x['level1'], x['level2']] for x in memoryData[f"list{secondGrid}"]], redraw=True)
                            sheet2.column_width(0, 400)
                            sheet2.column_width(1, 250)
                            sheet2.column_width(2, 250)
                            if secondGrid > 2: #MEANS THERE WAS NOT AUDIO FOR THESE STUDENT
                                playSoundList(listObj = memoryData[f"list{secondGrid}"], currGrid=currGrid, fillGrid=True)
                        if loadGrid == currList: #MEANS THE LAST LIST IS CURRENT
                            currGrid = sheet1
                            gridList = 1
                return True
        else:
            #GOT A LORA MESSAGE INSERTED INTO THE QUEUE
            bleMsgLst = bleMsg.split('|') 
            userInfo = getInfo(deviceID = f'{bleMsgLst[0]}{bleMsgLst[2]}', beacon=bleMsgLst[1], distance=bleMsgLst[3])
            if userInfo:
                jsonObj = userInfo
            else:
                jsonObj = {}
                return None
        externalNumber = f"{jsonObj['externalNumber']}"
        memoryData[f"list{currList}"].append(jsonObj)
        if currList < (loadGrid + 2):
            playSoundList([jsonObj], currGrid=currGrid)


def getInfo(beacon, distance, code:str=None, deviceID:str=None):
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
    elif deviceID:
        try:
            logging.debug(f'Student Lookup by DeviceID')
            name = df.loc[df['DeviceID'] == deviceID]
            if name.empty:
                logging.debug(f"Couldn't find DeviceID: {deviceID}")
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

def loadJson(inputStr: str) -> dict:
    result = None
    try:
        jsonObj = json.loads(inputStr)
        result = jsonObj
    except Exception as e:
        logging.debug(f'Error converting string {inputStr} to json - This might not be an issue')
        logging.debug(str(e))
    finally:
        return result

client.on_message = on_messageScreen;

client.connect(broker,
               port=myport,
               clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
               properties=properties,
               keepalive=60);

client.loop_start();
mytopic = 'IQSend'
client.subscribe(mytopic);

# Add a label to the window
main_label = tk.Label(root, text=f"Centerton Gamble Elementary - {datetime.now().strftime('%d %B, %Y')}",
                      font=("Arial", 30), fg="blue", bg="white")
label = tk.Label(root, text="0.0", font=("Arial", 30), fg="blue", bg="white")
label_call = FlashableLabel(root, text="Wait for your Name to be called", font=("Arial", 40), fg="white", bg="#6495ED")

main_label.grid(row=0, column=0, padx=130, pady=20, columnspan=2)
label.grid(row=0, column=1, padx=10, pady=10, sticky="ne", columnspan=2)
label_call.grid(row=1, column=0, padx=15, pady=15, columnspan=2)

labelGrid1 = tk.Label(root, text="Get Ready to Leave", font=("Arial", 30), fg="white", bg="#45B39D", width=38)
labelGrid1.grid(row=2, column=0, padx=40, pady=25, columnspan=1, sticky="nw")
labelGrid2 = tk.Label(root, text="Stand by (Next)", font=("Arial", 30), fg="white", bg="#EC7063", width=38)
labelGrid2.grid(row=2, column=1, padx=45, pady=25, columnspan=1, sticky="nw")

sheet1 = Sheet(root, headers=['Name', 'Grade', 'Teacher'], empty_vertical=0,
              width=880, height=700, font=("Arial", 24, "normal"), header_font=("Arial", 24, "normal"), table_bg="#45B39D", table_fg="black")
sheet1.column_width(0, 400)
sheet1.column_width(1, 200)
sheet1.column_width(2, 280)
sheet1.grid(row=3, column=0, padx=0, pady=0, columnspan=1, sticky="nw")

sheet2 = Sheet(root, headers=['Name', 'Grade', 'Teacher'], empty_vertical=0,
              width=880, height=700, font=("Arial", 24, "normal"), header_font=("Arial", 24, "normal"), table_bg = "#EC7063", table_fg="black")
sheet2.column_width(0, 400)
sheet2.column_width(1, 200)
sheet2.column_width(2, 280)
sheet2.grid(row=3, column=1, padx=10, pady=0, columnspan=1, sticky="nw")

currGrid = sheet1

# Start the real-time update loop
update_label()

# Run the main loop
root.mainloop()







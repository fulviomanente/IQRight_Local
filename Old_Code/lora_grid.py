import os
import tkinter as tk
from datetime import datetime
import time
from tksheet import Sheet
# import pyttsx3
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import pandas as pd
import json
from os.path import exists
import logging
import logging.handlers
from threading import Thread
import threading
import queue

# Import LORA Libraries
import busio
from digitalio import DigitalInOut, Direction, Pull
import board
# Import RFM9x
import adafruit_rfm9x

# LOGGING Setup
log_filename = "IQRight_FE.debug"
max_log_size = 20 * 1024 * 1024  # 20Mb
backup_count = 10
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
debug = True
handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=max_log_size, backupCount=backup_count)

handler.setFormatter(log_formatter)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)

class FlashableLabel(tk.Label):
    def flash(self, count):
        bg = self.cget('background')
        fg = self.cget('foreground')
        self.configure(background=fg, foreground=bg)
        count += 1
        if count < 5:
            self.after(1000, self.flash, count)

class SerialThread(Thread):
    def __init__(self, iqQueue):
        Thread.__init__(self)
        self._kill = threading.Event()
        self.queue = iqQueue
        # Configure LoRa Radio
        CS = DigitalInOut(board.CE1)
        RESET = DigitalInOut(board.D25)
        spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        self.rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, 915.23)
        self.rfm9x.tx_power = 23
        self.rfm9x.node = 1
        self.rfm9x.ack_delay = 0.1
        self.prev_packet = None
        logging.info('Connected to Lora Module')

        self.df = pd.read_csv('../data/full_load.iqr',
                              dtype={'ChildID': int, 'IDUser': int, 'FirstName': str, 'LastName': str, 'AppIDApprovalStatus': int \
                         , 'AppApprovalStatus': str, 'DeviceID': str, 'Phone': str, 'ChildName': str,
                            'ExternalNumber': str \
                         , 'HierarchyLevel1': str, 'HierarchyLevel1Type': str, 'HierarchyLevel1Desc': str \
                         , 'HierarchyLevel2': str, 'HierarchyLevel2Type': str, 'HierarchyLevel2Desc': str \
                         , 'StartDate': str, 'ExpireDate': str, 'IDApprovalStatus': int, 'ApprovalStatus': str
                         , 'MainContact': int, 'Relationship': str})

        logging.info('Loval DB Loaded into Dataframe')

    def getInfo(self, beacon, code, distance):
        if code:
            try:
                logging.debug(f'Student Lookup')
                name = self.df.loc[self.df['ExternalNumber'] == code]
                if name.empty:
                    logging.debug(f"Couldn't find Code: {code}")
                    return None
                else:
                    result = {"name": name['ChildName'].item(), "level1": name['HierarchyLevel1'].item(),
                              "level2": name['HierarchyLevel2'].item(),
                              "node": beacon, "externalID": code, "distance": abs(int(distance)),
                              "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                              "externalNumber": name['ExternalNumber'].item()}
                    return result
                # return {"node": beacon, "phoneID": code, "distance": abs(int(distance)), "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            except Exception as e:
                logging.error(f'Error converting string {beacon}|{code}|{distance} into MQTT Object')
                logging.error(f'{e}')
        else:
            logging.error(f'Empty string sent for conversion into MQTT Object')
        return None

    def handleInfo(self, strInfo: str):
        ret = False
        payload = None
        if len(strInfo) > 5:
            beacon, payload, distance = strInfo.split('|')
            if payload.find(":") >= 0:
                strCmd, command = payload.split(":")
                payload = {'command': command}
            else:
                sendObj = self.getInfo(beacon, payload, distance)
                payload = sendObj if sendObj else None
            if payload:
                ret = True
        return ret, payload

    def getGrade(self, strGrade: str):
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

    def sendDataScanner(self, payload: dict):
        startTime = time.time()
        while True:
            if 'name' in payload:
                msg = f"{payload['name']}|{self.getGrade(payload['level1'])}|{payload['level2']}"
            else:
                msg = f"cmd|ack|{payload['command']}"
                print(msg)
            if self.rfm9x.send_with_ack(bytes(msg, "UTF-8")):
                logging.debug('Info sent back')
                return True
            else:
                logging.debug(f"Failed to send Data to node: {msg}")
            if time.time() >= startTime + 5:
                logging.error(f"Timeout trying to send Data to node: {msg}")
                return False

    def run(self):
        try:
            while True:
                packet = None
                packet_text = None
                packet = self.rfm9x.receive(with_ack=True, with_header=True)
                if packet is not None:
                    self.prev_packet = packet[4:]
                    print(self.prev_packet)
                    try:
                        packet_text = str(self.prev_packet, "utf-8")
                    except Exception as e:
                        logging.error(f'{self.prev_packet}: Invalid byte String')
                        logging.error(f'{e.__str__()}')
                        packet_text = None
                    finally:
                        if packet_text:
                            if debug:
                                logging.debug(f'{packet} Received')
                                logging.debug(f'{packet_text} Converted to String')
                                logging.debug('RX: ')
                                logging.debug(packet_text)
                            result, payload = self.handleInfo(packet_text)
                            if result:
                                # IF ALL DATA COULD BE PARSED AND IDENTIFIED, SEND TO THE SCANNER
                                time.sleep(0.3)
                                if self.sendDataScanner(payload) == False:
                                    logging.error(f'FAILED to sent to Scanner: {json.dumps(payload)}')
                                else:
                                    sendObj = json.dumps(payload)
                                    self.queue.put(sendObj)
                            else:
                                logging.error(
                                    'No response received from MQ Topic: IQSend or Empty Message received from Lora')
                        else:
                            if debug:
                                logging.debug('Empty Package Received')
                        time.sleep(0.3)
                is_killed = self._kill.wait(1)
                if is_killed:
                    break

        except Exception as e:
            logging.info(e)

    def kill(self):
        self._kill.set()

class App(tk.Tk):
    def __init__(self):

        # Create the main window
        self.root = tk.Tk()
        self.root.title("Centerton Gamble Elementary")
        self.root.configure(bg='white')

        self.memoryData = {"list1": []}
        self.currList = 1
        self.gridList = 1
        self.loadGrid = 1

        self.sheet1 = Sheet(self.root, headers=['Name', 'Grade', 'Teacher'], empty_vertical=0,
                       width=900, height=700, font=("Arial", 24, "normal"), header_font=("Arial", 24, "normal"),
                       table_bg="#45B39D", table_fg="black")
        self.sheet1.column_width(0, 400)
        self.sheet1.column_width(1, 250)
        self.sheet1.column_width(2, 250)
        self.sheet1.grid(row=3, column=0, padx=10, pady=10, columnspan=1)

        self.sheet2 = Sheet(self.root, headers=['Name', 'Grade', 'Teacher'], empty_vertical=0,
                       width=900, height=700, font=("Arial", 24, "normal"), header_font=("Arial", 24, "normal"),
                       table_bg="#EC7063", table_fg="black")
        self.sheet2.column_width(0, 400)
        self.sheet2.column_width(1, 250)
        self.sheet2.column_width(2, 250)
        self.sheet2.grid(row=3, column=1, padx=10, pady=10, columnspan=1)

        self.currGrid = self.sheet1
        self.secondGrid = None

        # Add a label to the window
        self.main_label = tk.Label(self.root, text=f"Centerton Gamble Elementary - {datetime.now().strftime('%d %B, %Y')}",
                              font=("Arial", 30), fg="blue", bg="white")
        self.label = tk.Label(self.root, text="0.0", font=("Arial", 30), fg="blue", bg="white")
        self.label_call = self.FlashableLabel(self.root, text="Wait for your Name to be called", font=("Arial", 40), fg="white", bg="#6495ED")

        self.main_label.grid(row=0, column=0, padx=130, pady=20, columnspan=2)
        self.label.grid(row=0, column=1, padx=10, pady=10, sticky="ne", columnspan=2)
        self.label_call.grid(row=1, column=0, padx=15, pady=15, columnspan=2)

        self.labelGrid1 = tk.Label(self.root, text="Get Ready to Leave", font=("Arial", 30), fg="white", bg="#45B39D", width=40)
        self.labelGrid1.grid(row=2, column=0, padx=10, pady=25, columnspan=1)
        self.labelGrid2 = tk.Label(self.root, text="Stand by (Next)", font=("Arial", 30), fg="white", bg="#EC7063", width=40)
        self.labelGrid2.grid(row=2, column=1, padx=10, pady=25, columnspan=1)

        self.queue = queue.Queue()
        self.thread = SerialThread(self.queue)
        self.thread.start()
        self.process_serial()

        # Start the real-time update loop
        self.update_label()

    def update_label(self):
        # Update the label text
        self.label.config(text=f"{datetime.now().strftime('%H:%M:%S')}    ")
        # Schedule the next update in 100ms
        self.root.after(1000, self.update_label)

    def playSoundList(self, listObj, fillGrid: bool = False):
        for jsonObj in listObj:
            externalNumber = jsonObj['externalNumber']
            self.label_call.config(text=f"{jsonObj['name']} - {jsonObj['level1']}")
            self.currGrid.insert_row([jsonObj['name'], jsonObj['level1'], jsonObj['level2']], redraw=True)
            # rate = engine.getProperty('rate')
            # engine.setProperty('rate', 130)
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
                self.label_call.flash(0)
            if fillGrid:  # IF FILLING THE WHOLE GRID, SLEEP 2 SECONDS BEFORE PLAYING THE NEXT ONE
                time.sleep(2)

    def process_serial(self):
        value = True
        while self.queue.qsize():
            try:
                new = self.queue.get()
                logging.info('Read from Queue')
                logging.info(new)
                self.lbl_status.config(text=f"{new}")
                if value:
                    self.on_messageScreen(new)
                value = False
            except queue.Empty:
                logging.info("EMPTY QUEUE")
                pass
        self.after(100, self.on_messageScreen)

    def on_messageScreen(self, message):
        if self.debug:
            logging.debug('Message Received')
            logging.debug(str(message.payload, 'UTF-8'))
        jsonObj = json.loads(str(message.payload, 'UTF-8'))
        if 'command' in jsonObj:
            print(jsonObj)
            if jsonObj['command'] == 'break':
                if self.gridList == 1:
                    self.currGrid = self.sheet2
                    self.gridList = 2
                self.currList += 1
                self.memoryData[f"list{self.currList}"] = []
            elif jsonObj['command'] == 'release':
                # move grid 2 to grid 1
                self.sheet1.column_width(0, 400)
                self.sheet1.column_width(1, 250)
                self.sheet1.column_width(2, 250)
                self.sheet1.set_sheet_data(self.sheet2.get_sheet_data(), redraw=True, reset_col_positions=False)
                # empty grid 2
                self.sheet2.delete_rows([x for x in range(0, self.currGrid.get_total_rows())], deselect_all=True, redraw=True)
                self.loadGrid += 1
                self.secondGrid = self.loadGrid + 1
                if self.currList >= self.secondGrid:
                    self.sheet2.set_sheet_data([[x['name'], x['level1'], x['level2']] for x in self.memoryData[f"list{self.secondGrid}"]],
                                          redraw=True)
                    self.sheet2.column_width(0, 400)
                    self.sheet2.column_width(1, 250)
                    self.sheet2.column_width(2, 250)
                    if self.secondGrid > 2:  # MEANS THERE WAS NOT AUDIO FOR THESE STUDENT
                        self.playSoundList(listObj=self.memoryData[f"list{self.secondGrid}"], fillGrid=True)
                if self.loadGrid == self.currList:  # MEANS THE LAST LIST IS CURRENT
                    self.currGrid = self.sheet1
                    self.gridList = 1

        else:
            print(jsonObj)
            self.memoryData[f"list{self.currList}"].append(jsonObj)
            print(self.memoryData)
            if self.currList < (self.loadGrid + 2):
                self.playSoundList([jsonObj])

# Run the main loop
app = App()
app.mainloop()

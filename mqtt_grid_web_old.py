#mqtt_grid_web_old.py

import datetime
import os
from datetime import datetime, timedelta
import time
import paho.mqtt.client as mqtt
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes
# import pyttsx3
from gtts import gTTS
# from pydub import AudioSegment
# from pydub.playback import play
import json
import logging
import logging.handlers
from flask import Flask, render_template, request, redirect, url_for, flash, g, abort, session, jsonify, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_socketio import SocketIO
from forms import ChangePasswordForm
from flask_babel import Babel, gettext as _
from dotenv import load_dotenv
from utils.config import TOPIC_PREFIX, TOPIC, API_URL, IDFACILITY, LORASERVICE_PATH, DEBUG
from utils.offline_data import OfflineData
from utils.api_client import api_request, get_secret
import io

app = Flask(__name__)
app.secret_key = '1QrightS3cr3tKey'  # Secret key for session management
app.config.from_pyfile('utils/config.py')
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
babel = Babel(app)
socketio = SocketIO(app)

load_dotenv()

lastCommand = ''
lastCommandTimestamp = datetime.now()

# User class (for Flask-Login)
class User(UserMixin):
    def __init__(self, id, class_codes):
        self.id = id
        self.class_codes = class_codes

#######################################################################################
##################### GENERAL UTILITY METHODS #########################################

#@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(['en', 'es', 'de'])

    #if g.lang_code:
    #    return g.lang_code
    #else:
    #    return "en"

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(Exception)
def handle_error(e):
    if (str(e) == '504'):
        session['authentication_status'] = False
        flash(_('Session has expired, please login again'), 'error')
        return redirect(url_for("/login"))

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


#######################################################################################
##################### IQRIGHT METHODS #########################################

def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        logging.debug(f"MQTT CONNECTION: Connected to MQTT Broker")
        # Subscribe to class queues for the logged-in user
        if userdata.get('userAuthenticated') and userdata.get('classCode'):
            topic = f"{TOPIC_PREFIX}{userdata.get('classCode')}"
            client.subscribe(topic)
            logging.debug(f"MQTT CONNECTION: User {userdata.get('userName', 'unknown')} Subscribed to topic: {topic}")
            
            # Also subscribe to a test topic for debugging
            test_topic = f"{TOPIC_PREFIX}test"
            client.subscribe(test_topic)
            logging.debug(f"MQTT CONNECTION: Subscribed to test topic: {test_topic}")
    else:
        logging.debug(f"MQTT CONNECTION: Failed to connect, return code %d\n", rc)
        print()

def authenticate_user(username, password):
    payload = {
        'Username': username,
        'Password': password,
        'showDependents': False,
        'showHierarchy': True
    }
    errorMsg = None

    returnCode, info = api_request(method="POST", url='apiGetSession', data=payload)

    offlineData = OfflineData()

    if info['message']:
        #IF THERE IS NO CONNECTIVITY TRY TO LOGIN OFFLINE
        if returnCode > 400:
            errorMsg = info['message']
            info = offlineData.findUser(userName=username)
        else:
            if info:
                if returnCode == 200:
                    errorMsg = None
                    # Validate if the Login matches the facility
                    facilities = [x['idFacility'] for x in info['listFacilities']]
                    if int(IDFACILITY) in facilities:
                        # Validate if the user can see the Students Grid
                        if 'StudentGrid' not in info.get('roles'):
                            errorMsg = 'User does not have enough permision to access the Student Grid'
                            # TODO: "changePassword": true,
                            # "homeSetup": [
                            #    {
                            #        "card": 0,
                            #        "metric": "string"
                            #    }
                    else:
                        errorMsg = 'User does not have enough permision to access this Facility Data'
                else:
                    jsonErrorMsg = json.loads(info['message'])
                    errorMsg = f"{jsonErrorMsg.get('message', '')}, {jsonErrorMsg.get('result', '')}"
            else:
                errorMsg = 'User not found!'
    else:
        errorMsg = 'Unexpected Service Return: ' + json.dumps(info)
    if errorMsg:
        return {'authenticated': False, 'classCodes': [], 'errorMsg': errorMsg, 'changePassword': False, 'newUser': False, 'fullName': ''}
    else:
        return {'authenticated': True, 'classCodes': info['listHierarchy'], 'errorMsg': None, 'changePassword': info.get('changePassword', False), 'newUser': info.get('newUser', False), 'fullName': info.get('fullName', ' ')}

def on_messageScreen(client, userdata, message, tmp=None):
    global lastCommand
    global lastCommandTimestamp
    
    # Always log incoming messages regardless of DEBUG setting
    logging.debug(f'Message Received on topic: {message.topic}')
    payload_str = str(message.payload, 'UTF-8')
    logging.debug(f'Payload: {payload_str}')
    
    # Try to parse the payload as JSON
    jsonObj = loadJson(payload_str)
    if isinstance(jsonObj, dict):
        logging.debug(f'Valid JSON received: {jsonObj}')
        if 'command' in jsonObj:
            if lastCommand != jsonObj['command'] or (datetime.now() - lastCommandTimestamp).total_seconds() > 6:
                 lastCommand = jsonObj['command']
                 lastCommandTimestamp = datetime.now()
                 # Publish to the sockeio service so the JS can read it and update the HTML
                 userInfo = {"cmd": jsonObj['command']}
                 socketio.emit('new_data', userInfo)
                 logging.debug(f'Emitted command to socketio: {jsonObj["command"]}')
        else:
            # Publish to the sockeio service so the JS can read it and update the HTML
            try:
                userInfo = {"fullName": jsonObj.get("name", "Unknown"), "location": jsonObj.get("location", "Unknown"), "externalNumber": jsonObj.get("externalNumber", "000000")}
                socketio.emit('new_data', userInfo)
                logging.debug(f'Emitted data to socketio: {userInfo}')
            except Exception as e:
                logging.error(f'Error emitting user info to socketio: {e}')
        return True
    else:
        logging.debug('NOT A VALID JSON OBJECT RECEIVED FROM QUEUE')
        return False
     #externalNumber = f"{jsonObj['externalNumber']}"
#     memoryData[f"list{currList}"].append(jsonObj)
#     if currList < (loadGrid + 2):
#         playSoundList([jsonObj], currGrid=currGrid)


def getInfo(beacon, distance, code: str = None, deviceID: str = None):
    if code:
        df = OfflineData.getAppUsers()
        try:
            logging.debug(f'Student Lookup')
            name = df.loc[df['ExternalNumber'] == code]
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
    elif deviceID:
        try:
            logging.debug(f'Student Lookup by DeviceID')
            name = df.loc[df['DeviceID'] == deviceID]
            if name.empty:
                logging.debug(f"Couldn't find DeviceID: {deviceID}")
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
    else:
        logging.error(f'Empty string sent for conversion into MQTT Object')
        return None

def playSoundList(listObj, currGrid, fillGrid: bool = False):
    for jsonObj in listObj:
        externalNumber = jsonObj['externalNumber']
        label_call.config(text=f"{jsonObj['name']} - {jsonObj['level1']}")
        currGrid.insert_row([jsonObj['name'], jsonObj['level1'], jsonObj['level2']], redraw=True)
        # rate = engine.getProperty('rate')
        # engine.setProperty('rate', 130)
        if os.path.exists(f'./Sound/{externalNumber}.mp3') == False:
            logging.info(f'Missing Audio File - {externalNumber}.mp3')
            logging.info(f'Generating from Google')
            tts = gTTS(f"{jsonObj['level1']}, {jsonObj['name']}", lang='en')
            tts.save(f'./Sound/{externalNumber}.mp3')
        else:
            if os.environ.get("MAC", None) != None:
                print(f'Calling {externalNumber}')
            else:
                #song = AudioSegment.from_file(f'./Sound/{externalNumber}.mp3', format="mp3")
                #play(song)
                print ("oi")
            label_call.flash(0)
        if fillGrid:  # IF FILLING THE WHOLE GRID, SLEEP 2 SECONDS BEFORE PLAYING THE NEXT ONE
            time.sleep(2)

# LOGGING Setup
log_filename = "IQRight_FE_WEB.debug"
max_log_size = 20 * 1024 * 1024  # 20Mb
backup_count = 10
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
debug = DEBUG == 'TRUE'
handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=max_log_size, backupCount=backup_count)

handler.setFormatter(log_formatter)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)

lastCommand = None

babel.init_app(app, locale_selector=get_locale)

version = '5'  # or '3'
mytransport = 'tcp'  # 'websockets' # or 'tcp'

#Get credentials from Secret Manager
client = mqtt.Client(client_id="IQRight_Main", transport=mytransport, protocol=mqtt.MQTTv5)
mqttUsername = get_secret('mqttUsername').get('value', '')
mqttpassword = get_secret('mqttpassword').get('value', '')
client.username_pw_set(mqttUsername, mqttpassword)
client.on_connect = on_connect
client.on_message = on_messageScreen

broker = 'localhost'  # eg. choosen-name-xxxx.cedalo.cloud
myport = 1883
properties = Properties(PacketTypes.CONNECT)
properties.SessionExpiryInterval = 30 * 60  # in seconds

memoryData = {"list1": []}
currList = 1
gridList = 1
loadGrid = 1

AUTH_SERVICE_URL = get_secret('authServiceUrl')

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User loader function for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User(user_id, class_codes=session.get('_classCodeList', [0])) #current_user.class_codes)

#######################################################################################
##################### FLASK URL ROUTE METHODS #########################################

# Route for ChangePassword page
@app.route("/change-password", methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if request.method == "POST" and form.validate():
        payload = {"userName": session['_user_id'], "currentPassword": form.current_password.data, "newPassword": form.new_password.data}
        status_code, response = api_request("POST", 'apiUpdateUserPassword/', payload)
        if status_code == 200:
            flash(response['message'], 'success')
            session['changePassword'] = False
            return redirect(url_for('home'))
        else:
            flash(json.loads(response['message'])['message'], 'error')
            return redirect(url_for('change_password'))


    return render_template('change-password.html', form = form)

# Route for login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Call backend service for authentication
        response = authenticate_user(username, password)

        if response['authenticated']:
            classCodes = [int(x['IDHierarchy']) for x in response['classCodes']]
            mainClassCode = int(classCodes[0]) if classCodes else 0
            user = User(username, classCodes if classCodes else [0])
            login_user(user, duration = 600)
            session['_newUser'] = response.get('newUser')
            session['fullName'] = response.get('fullName')
            session['_classCode'] = mainClassCode
            session['_classCodeList'] = classCodes
            if session['_newUser']:
                'Call the reset service to create a temporary password and send it to the user'
                payload = {'userName': username}
                returnCode, info = api_request(method="POST", url='apiUpdatePasswordReset', data=payload)
                if returnCode == 200:
                    flash(f'{info.get("message")}', 'success')
                else:
                    flash(f'Please try resetting your password manually before continuing. Access Denied!')
                return redirect(url_for('login'))

            elif response.get('changePassword'):
                return redirect(url_for('change_password'))

            else:
                return redirect(url_for('home'))

        else:
            flash(f'Invalid Login Attempt. {response["errorMsg"]}' )
            return redirect(url_for('login'))

    return render_template('login.html')


# Function to authenticate user by calling the backend service

# Route for the real-time data grid (requires login)
@app.route('/')
@app.route('/home')
@login_required
def home():
    try:
        # Make sure client is not already connected
        if client.is_connected():
            try:
                client.disconnect()
                logging.debug("Disconnected existing MQTT client before reconnecting")
            except Exception as disconnect_err:
                logging.error(f"Error disconnecting MQTT client: {disconnect_err}")
        
        # Set user data with complete information
        user_data = {
            "userAuthenticated": current_user.is_authenticated, 
            'classCode': session.get('_classCode', 0),
            'userName': current_user.id
        }
        client.user_data_set(user_data)
        
        # Log connection attempt
        logging.debug(f"Connecting to MQTT broker at {broker}:{myport} with user data: {user_data}")
        
        # Connect to broker
        client.connect(broker,
                       port=myport,
                       clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
                       properties=properties,
                       keepalive=60)
        
        # Start loop in a background thread
        client.loop_start()
        
        logging.debug(f"MQTT client connected and loop started for user {current_user.id}")
        
        return render_template('index.html', class_codes=[str(x) for x in current_user.class_codes], newUser=session['_newUser'], fullName=session['fullName'])

    except Exception as e: #Catch MQTT connection errors
        logging.error(f"MQTT Connection Error in /home: {e}")
        return render_template('mqtt_error.html')  # Render error page


# Route for logging out
@app.route('/logout')
@login_required
def logout():
    logout_user()
    try:
        # Need to specify topic when unsubscribing
        if client.is_connected():
            class_code = session.get('_classCode', 0)
            topic = f"{TOPIC_PREFIX}{class_code}"
            client.unsubscribe(topic)
            client.unsubscribe(f"{TOPIC_PREFIX}test")  # Also unsubscribe from test topic
            client.disconnect()
            logging.debug(f"MQTT: Unsubscribed from topic {topic} and disconnected")
    except Exception as e: #Catch MQTT connection errors
        logging.error(f"MQTT Connection Error in /logout (unsubscribe): {e}")
    finally:
        return redirect(url_for('login'))

@app.route('/getAudio/<external_number>')
def get_audio(external_number):
    try:
        # 1. First try to get the existing local file
        local_file_path = f'./Sound/{external_number}.mp3'
        if os.path.exists(local_file_path):
            logging.debug(f"Serving existing local audio file for {external_number}")
            return send_file(local_file_path, mimetype='audio/mpeg')
        
        # 2. If local file doesn't exist, try to get from integration layer
        logging.debug(f"Local file not found, requesting from integration layer for {external_number}")
        status_code, response = api_request(
            method="GET", 
            url=f'apiGetAudio/{external_number}',
            is_file=True  # Assuming api_request handles file downloads differently
        )
        
        if status_code == 200 and response:
            # Save the received file locally
            try:
                with open(local_file_path, 'wb') as f:
                    f.write(response)
                logging.debug(f"Saved audio file from integration layer for {external_number}")
                return send_file(local_file_path, mimetype='audio/mpeg')
            except Exception as save_error:
                logging.error(f"Error saving audio file from integration: {save_error}")
                # Continue to gTTS fallback
        
        # 3. If integration layer fails, generate using gTTS
        logging.debug(f"Integration layer failed, generating audio with gTTS for {external_number}")
        df = OfflineData.getAppUsers()
        student = df.loc[df['ExternalNumber'] == external_number]
        
        if student.empty:
            text_to_speak = f"Student {external_number}"
        else:
            text_to_speak = f"{student['level1'].item()}, {student['ChildName'].item()}"
        
        # Generate audio using gTTS
        tts = gTTS(text_to_speak, lang='en')
        
        # Save to BytesIO object and file system
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        
        # Save to file system for future use
        tts.save(local_file_path)
        logging.debug(f"Generated and saved gTTS audio for {external_number}")
        
        return send_file(
            audio_bytes,
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name=f'{external_number}.mp3'
        )
        
    except Exception as e:
        logging.error(f"Error in audio generation pipeline for {external_number}: {str(e)}")
        return jsonify({'error': 'Failed to generate audio'}), 500

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
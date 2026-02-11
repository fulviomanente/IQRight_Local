#mqtt_grid_web.py

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
import io

from utils.config import TOPIC_PREFIX, TOPIC, API_URL, IDFACILITY, DEBUG
from utils.offline_data import OfflineData
from utils.api_client import api_request, get_secret

app = Flask(__name__)
app.secret_key = '1QrightS3cr3tKey'  # Secret key for session management
app.config.from_pyfile('utils/config.py')
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
babel = Babel(app)
socketio = SocketIO(app, cors_allowed_origins="*")  # Allow cross-origin for all domains
offlineData = OfflineData()

load_dotenv()

# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    logging.info(f'[SOCKETIO] Client connected: sid={request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    logging.info(f'[SOCKETIO] Client disconnected: sid={request.sid}')

@socketio.on('join')
def on_join(data):
    user_id = data.get('user_id')
    if not user_id:
        logging.warning(f'[SOCKETIO] Join request without user_id (sid={request.sid})')
        return

    socketio.server.enter_room(request.sid, user_id)
    logging.info(f'[SOCKETIO] User {user_id} joined room (sid={request.sid})')

    # Verify MQTT client health — recreate if dead
    mqtt_healthy = (user_id in mqtt_clients and
                    mqtt_clients[user_id].is_connected())

    if not mqtt_healthy:
        logging.warning(f'[MQTT-HEALTH] MQTT client dead for {user_id} on SocketIO rejoin - recreating')
        _setup_mqtt_client(user_id)

@socketio.on('release_complete')
def handle_release_complete(data):
    """Handle client notification that release processing is complete"""
    user_id = data.get('user_id')
    if not user_id:
        return

    logging.debug(f'Release processing complete for user {user_id}')

    # If there's any pending data to send to this user, we can send it now
    if user_id in memory_data_store:
        memory_data = memory_data_store[user_id]
        # Mark that this user has completed release processing
        memory_data.release_pending = False
        logging.debug(f'User {user_id} is ready to receive new data')

        # Send any pending data from the second list to fill the right column
        if len(memory_data.virtualList) > 1 and len(memory_data.virtualList[1]) > 0:
            logging.debug(f'Sending break signal')
            command = {"cmd": "break"}
            socketio.emit('new_data', command, room=user_id)
            logging.debug(f'Sending {len(memory_data.virtualList[1])} pending items to user: {user_id}')
            for userInfo in memory_data.virtualList[1]:
                # Emit to specific user's room
                socketio.emit('new_data', userInfo, room=user_id)
                logging.debug(f'Emitted pending data to socketio for user {user_id}: {userInfo}')

# LOGGING Setup
log_filename = "logs/IQRight_FE_WEB.debug"
max_log_size = 20 * 1024 * 1024  # 20Mb
backup_count = 10
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
debug = DEBUG
handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=max_log_size, backupCount=backup_count)

handler.setFormatter(log_formatter)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)


# User class (for Flask-Login)
class User(UserMixin):
    def __init__(self, id, class_codes):
        self.id = id
        self.class_codes = class_codes

class Virtual_List():
    def __init__(self, user_id=None):
        self.virtualList = [[]]
        self.currList = 0
        self.lastCommand = ''
        self.lastCommandTimestamp = datetime.now()
        self.screenFull = False
        self.user_id = user_id
        self.release_pending = False  # Track if a release is in progress

    def publish_command(self, jsonObj):
        try:
            userInfo = {"cmd": jsonObj['command']}
            if self.user_id:
                socketio.emit('new_data', userInfo, room=self.user_id)
                logging.debug(f'Emitted command to socketio for user {self.user_id}: {jsonObj["command"]}')
            else:
                socketio.emit('new_data', userInfo)
                logging.debug(f'Emitted command to socketio (no user ID): {jsonObj["command"]}')
        except Exception as e:
            logging.error(f'Error emitting user info to socketio: {e}')

    def publish_data(self, jsonObj):
        #Check if it should send it to the screen
        userInfo = {"fullName": jsonObj.get("name", "Unknown"), "location": jsonObj.get("location", "Unknown"), "externalNumber": jsonObj.get("externalNumber", "000000")}
        logging.info(f'[PUBLISH] User {self.user_id}: Processing data: {userInfo}')

        # Store in memory regardless of whether we display it now
        if self.currList < len(self.virtualList):
            self.virtualList[self.currList].append(userInfo)
            logging.info(f'[PUBLISH] User {self.user_id}: Added to virtualList[{self.currList}], now has {len(self.virtualList[self.currList])} items')
        else:
            # Ensure we have a valid index
            self.virtualList.append([])
            self.virtualList[self.currList].append(userInfo)
            logging.info(f'[PUBLISH] User {self.user_id}: Created new list [{self.currList}], added first item')

        # Don't emit if a release is pending - client will request the data when ready
        if self.release_pending:
            logging.warning(f'[PUBLISH] User {self.user_id}: NOT emitting - release_pending=True. Data stored for later.')
            return

        # Check if screen can accept more data
        list_count = len(self.virtualList)
        list2_empty = len(self.virtualList[2]) == 0 if list_count > 2 else True
        can_emit = (list_count < 3) or (list_count == 3 and list2_empty)
        logging.info(f'[PUBLISH] User {self.user_id}: list_count={list_count}, list2_empty={list2_empty}, can_emit={can_emit}')

        if can_emit:
            # Publish to the socketio service so the JS can read it and update the HTML
            try:
                if self.user_id:
                    socketio.emit('new_data', userInfo, room=self.user_id)
                    logging.info(f'[SOCKETIO-TX] SUCCESS: Emitted to room {self.user_id}: {userInfo}')
                else:
                    socketio.emit('new_data', userInfo)
                    logging.info(f'[SOCKETIO-TX] SUCCESS: Emitted broadcast (no room): {userInfo}')
            except Exception as e:
                logging.error(f'[SOCKETIO-TX] FAILED: Error emitting for user {self.user_id}: {e}', exc_info=True)
        else:
            logging.warning(f'[PUBLISH] User {self.user_id}: NOT emitting - screen full (list_count={list_count})')

        self.lastCommand = ''

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
        logging.info(f"[MQTT-CONN] Connected to MQTT Broker successfully")

        # Subscribe to the central command queue for all users with QoS 1 for reliability
        command_topic = f"IQRSend"
        result, mid = client.subscribe(command_topic, qos=1)
        logging.info(f"[MQTT-SUB] User {userdata.get('userName', 'unknown')} subscribed to command topic: {command_topic} (result={result}, mid={mid}, QoS=1)")

        # Subscribe to class-specific queues for the logged-in user (for student data)
        if userdata.get('userAuthenticated') and userdata.get('classCode'):
            topic = f"{TOPIC_PREFIX}{userdata.get('classCode')}"
            result, mid = client.subscribe(topic, qos=1)
            logging.info(f"[MQTT-SUB] User {userdata.get('userName', 'unknown')} subscribed to topic: {topic} (result={result}, mid={mid}, QoS=1)")

            # Also subscribe to a test topic for debugging
            test_topic = f"{TOPIC_PREFIX}test"
            result, mid = client.subscribe(test_topic, qos=1)
            logging.info(f"[MQTT-SUB] Subscribed to test topic: {test_topic} (result={result}, mid={mid}, QoS=1)")

            # Send handshake to verify end-to-end MQTT pipeline with CaptureLora
            handshake_payload = json.dumps({
                "type": "web_hello",
                "classCode": str(userdata.get('classCode')),
                "userName": userdata.get('userName')
            })
            client.publish("IQRHandshake", handshake_payload, qos=1)
            logging.info(f"[MQTT-HANDSHAKE] Sent web_hello for user {userdata.get('userName')}, classCode={userdata.get('classCode')}")
    else:
        logging.error(f"[MQTT-CONN] Failed to connect, return code: {rc}")

def on_mqtt_disconnect(client, userdata, flags, rc, properties=None):
    """Detect and log MQTT disconnections for debugging and health tracking."""
    user_id = userdata.get('userName', 'unknown') if userdata else 'unknown'
    if rc == 0:
        logging.info(f"[MQTT-CONN] Clean disconnect for user {user_id}")
    else:
        logging.warning(f"[MQTT-CONN] Unexpected disconnect for user {user_id}, rc={rc}. Auto-reconnect will attempt.")


def _setup_mqtt_client(user_id):
    """Create or recreate MQTT client for a user. Called from /home and on_join."""
    # Clean up existing client
    if user_id in mqtt_clients:
        try:
            mqtt_clients[user_id].loop_stop()
            if mqtt_clients[user_id].is_connected():
                mqtt_clients[user_id].disconnect()
            logging.debug(f"Cleaned up old MQTT client for {user_id}")
        except Exception as e:
            logging.error(f"Error cleaning up MQTT client for {user_id}: {e}")

    client_id = f"IQRight_{user_id}"
    client = mqtt.Client(client_id=client_id, transport=mytransport, protocol=mqtt.MQTTv5)
    client.username_pw_set(mqttUsername, mqttpassword)
    client.on_connect = on_connect
    client.on_message = on_messageScreen
    client.on_disconnect = on_mqtt_disconnect

    class_code = session.get('_classCode', 0)
    user_data = {
        "userAuthenticated": True,
        "classCode": class_code,
        "userName": user_id
    }
    client.user_data_set(user_data)

    client.connect(broker, port=myport,
                   clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
                   properties=properties, keepalive=60)
    client.loop_start()
    mqtt_clients[user_id] = client

    # Create user-specific memory data if it doesn't exist
    if user_id not in memory_data_store:
        memory_data_store[user_id] = Virtual_List(user_id=user_id)

    logging.info(f"[MQTT-SETUP] Client created for {user_id}, client_id={client_id}, classCode={class_code}")


def authenticate_user(username, password):
    payload = {
        'Username': username,
        'Password': password,
        'showDependents': False,
        'showHierarchy': True
    }
    errorMsg = None

    returnCode, info = api_request(method="POST", url='apiGetSession', data=payload)

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
    try:
        # Always log incoming messages at INFO level for traceability
        logging.info(f'[MQTT-RX] Topic: {message.topic}, QoS: {message.qos}, Retain: {message.retain}')
        payload_str = str(message.payload, 'UTF-8')
        logging.info(f'[MQTT-RX] Payload: {payload_str}')

        # Ensure userdata contains the user_id to identify the session
        user_id = userdata.get('userName')
        if not user_id:
            logging.error("[MQTT-RX] Message received but no user_id in userdata - DROPPING")
            return False

        # Check if this is a command message from the central command queue
        command_topic = f"IQRSend"
        if message.topic == command_topic:
            logging.info(f'[MQTT-RX] Command message detected, broadcasting to all clients')
            # Process command message and broadcast to all clients
            return process_command_message(payload_str)

        # Try to parse the payload as JSON
        jsonObj = loadJson(payload_str)

        # Handle handshake ACK (not student data)
        if isinstance(jsonObj, dict) and jsonObj.get('type') == 'web_hello_ack':
            logging.info(f'[MQTT-HANDSHAKE] ACK received for user {user_id} - pipeline confirmed')
            socketio.emit('connection_status', {'status': 'connected', 'timestamp': jsonObj.get('timestamp')}, room=user_id)
            return True

        # Get the memory data for this user, or create if not exists
        if user_id not in memory_data_store:
            logging.info(f'[MQTT-RX] Creating new Virtual_List for user: {user_id}')
            memory_data_store[user_id] = Virtual_List(user_id=user_id)

        memory_data = memory_data_store[user_id]

        if isinstance(jsonObj, dict):
            logging.info(f'[MQTT-RX] Valid JSON for user {user_id}: {jsonObj}')
            # For student queue messages, just process the data (not commands)
            if 'command' not in jsonObj:
                logging.info(f'[MQTT-RX] Calling publish_data for user {user_id}')
                memory_data.publish_data(jsonObj)
                return True
            else:
                # Handle commands that might come from non-central queues (for backward compatibility)
                logging.warning(f'[MQTT-RX] Command received on non-command queue: {jsonObj["command"]}. Ignoring.')
                return True
        else:
            logging.error(f'[MQTT-RX] NOT A VALID JSON OBJECT: {payload_str}')
            return False

    except Exception as e:
        logging.error(f'[MQTT-RX] UNHANDLED EXCEPTION in on_messageScreen: {e}', exc_info=True)
        return False

def process_command_message(payload_str):
    """Process a command message from the central command queue and broadcast to all clients"""
    jsonObj = loadJson(payload_str)
    if not isinstance(jsonObj, dict) or 'command' not in jsonObj:
        logging.error(f'Invalid command message format: {payload_str}')
        return False

    command = jsonObj['command']
    logging.debug(f'Broadcasting command to all users: {command}')

    # Update all memory_data objects
    for user_id, memory_data in memory_data_store.items():
        # Only process if this is a new command or enough time has passed
        if memory_data.lastCommand != command or (datetime.now() - memory_data.lastCommandTimestamp).total_seconds() > 6:
            memory_data.lastCommand = command
            memory_data.lastCommandTimestamp = datetime.now()

            # Handle break command
            if command == 'break':
                memory_data.currList += 1
                memory_data.virtualList.append([])
                memory_data.publish_command(jsonObj)
                if len(memory_data.virtualList) > 2:
                    memory_data.screenFull = True

            # Handle release command
            elif command == 'release':
                ready2leave = memory_data.virtualList.pop(0) if memory_data.virtualList else []
                if memory_data.currList > 0:
                    memory_data.currList -= 1

                # Mark that a release is in progress
                memory_data.release_pending = True
                logging.debug(f'Setting release_pending to True for user {user_id}')

                # Publish to the socketio service
                memory_data.publish_command(jsonObj)

                # Initialize the second list if it doesn't exist yet
                if len(memory_data.virtualList) < 2:
                    memory_data.virtualList.append([])

                if len(memory_data.virtualList) < 2:
                    memory_data.screenFull = False

            # Handle clean command or any other commands
            elif command == 'clean':
                memory_data.publish_command(jsonObj)

        else:
            logging.debug(f'Command already processed for user {user_id}')
            logging.debug(f'Last Command: {memory_data.lastCommand}, Last Command Timestamp: {memory_data.lastCommandTimestamp}, New Command: {command}')
            logging.debug(f'New Command: {memory_data.lastCommand != command}')

    return True


def getInfo(beacon, distance, code: str = None, deviceID: str = None):
    df = offlineData.getAppUsers()
    if code:
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


babel.init_app(app, locale_selector=get_locale)

version = '5'  # or '3'
mytransport = 'tcp'  # 'websockets' # or 'tcp'

# Configure MQTT properties
broker = 'localhost'  # eg. choosen-name-xxxx.cedalo.cloud
myport = 1883
properties = Properties(PacketTypes.CONNECT)
properties.SessionExpiryInterval = 30 * 60  # in seconds

# Get credentials from Secret Manager
mqttUsername = get_secret('mqttUsername').get("value", "IQRight")
mqttpassword = get_secret('mqttpassword').get("value", "123456")

# Dictionary to store per-user MQTT clients
mqtt_clients = {}
# Dictionary to store per-user memory data
memory_data_store = {}

AUTH_SERVICE_URL = get_secret('authServiceUrl').get("value", "https://integration.iqright.app/api")

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
        user_id = current_user.id
        _setup_mqtt_client(user_id)

        return render_template('index.html',
                              user_id=user_id,
                              class_codes=[str(x) for x in current_user.class_codes],
                              newUser=session['_newUser'],
                              fullName=session['fullName'],
                              current_user=current_user)

    except Exception as e:
        logging.error(f"MQTT Connection Error in /home: {e}", exc_info=True)
        return render_template('mqtt_error.html')

#Route to retrieve and play the sound
@app.route('/getAudio/<external_number>')
def get_audio(external_number):
    try:
        # 1. First try to get the existing local file
        local_file_path = f'./static/sounds/{external_number}.mp3'
        if os.path.exists(local_file_path):
            logging.debug(f"Serving existing local audio file for {external_number}")
            return send_file(local_file_path, mimetype='audio/mpeg')

        # 2. If local file doesn't exist, try to get from integration layer
        #logging.debug(f"Local file not found, requesting from integration layer for {external_number}")
        #status_code, response = api_request(method="POST", url='apiGetAudio', data='{"key": ' + external_number + '}', is_file=True)

        #if status_code == 200 and response:
        #    # Save the received file locally
        #    try:
        #        with open(local_file_path, 'wb') as f:
        #            f.write(response)
        #        logging.debug(f"Saved audio file from integration layer for {external_number}")
        #        return send_file(local_file_path, mimetype='audio/mpeg')
        #    except Exception as save_error:
        #        logging.error(f"Error saving audio file from integration: {save_error}")
                # Continue to gTTS fallback

        # 3. If integration layer fails, generate using gTTS
        else:
            logging.debug(f"Integration layer failed, generating audio with gTTS for {external_number}")
            df = offlineData.getAppUsers()
            student = df[df['ExternalNumber'] == external_number].iloc[0]

            if student.empty:
                text_to_speak = f"Atention!! Student called on, Gym side"
            else:
                text_to_speak = f"{student['ChildName']}, Gym Side"

            # Generate audio using gTTS — single API call, save to disk, serve from file
            tts = gTTS(text_to_speak, lang='en')
            tts.save(local_file_path)
            logging.debug(f"Generated and saved gTTS audio for {external_number}")

            return send_file(local_file_path, mimetype='audio/mpeg')

    except Exception as e:
        logging.error(f"Error in audio generation pipeline for {external_number}: {str(e)}")
        return jsonify({'error': 'Failed to generate audio'}), 500


# Route to get students for Watcher of the Day dropdown
@app.route('/api/students')
@login_required
def get_students():
    """Returns students filtered by the teacher's class codes (IDHierarchy)"""
    try:
        class_codes = session.get('_classCodeList', [])
        if not class_codes:
            return jsonify({'students': [], 'error': 'No class codes found'})

        df = offlineData.getAppUsers()
        if df is None or df.empty:
            return jsonify({'students': [], 'error': 'No student data available'})

        # Filter students by IDHierarchy matching teacher's class codes
        # Convert class_codes to strings for comparison
        class_codes_str = [str(code) for code in class_codes]

        # Check if IDHierarchy column exists
        if 'IDHierarchy' in df.columns:
            filtered_df = df[df['IDHierarchy'].astype(str).isin(class_codes_str)]
        elif 'HierarchyLevel1' in df.columns:
            # Fallback to HierarchyLevel1 if IDHierarchy doesn't exist
            filtered_df = df[df['HierarchyLevel1'].astype(str).isin(class_codes_str)]
        else:
            logging.error("No hierarchy column found in student data")
            return jsonify({'students': [], 'error': 'No hierarchy column found'})

        # Get unique student names sorted alphabetically
        students = filtered_df[['ChildName', 'ExternalNumber']].drop_duplicates()
        students = students.sort_values('ChildName')

        student_list = [
            {'name': row['ChildName'], 'id': row['ExternalNumber']}
            for _, row in students.iterrows()
        ]

        return jsonify({'students': student_list})
    except Exception as e:
        logging.error(f"Error getting students for watcher: {str(e)}")
        return jsonify({'students': [], 'error': str(e)})


# Route for logging out
@app.route('/logout')
@login_required
def logout():
    user_id = current_user.id
    try:
        # Clean up user's MQTT client if it exists
        if user_id in mqtt_clients and mqtt_clients[user_id].is_connected():
            # Need to specify topic when unsubscribing
            class_code = session.get('_classCode', 0)
            topic = f"{TOPIC_PREFIX}{class_code}"
            command_topic = f"IQRSend"

            # Unsubscribe from all topics
            mqtt_clients[user_id].unsubscribe(topic)
            mqtt_clients[user_id].unsubscribe(command_topic)
            mqtt_clients[user_id].unsubscribe(f"{TOPIC_PREFIX}test")  # Also unsubscribe from test topic

            mqtt_clients[user_id].disconnect()
            logging.debug(f"MQTT: Unsubscribed user {user_id} from topic {topic}, {command_topic} and disconnected")

            # Remove client from dictionary
            del mqtt_clients[user_id]

            # Clean up memory data
            if user_id in memory_data_store:
                del memory_data_store[user_id]

            logging.debug(f"Cleaned up MQTT resources for user {user_id}")
    except Exception as e: # Catch MQTT connection errors
        logging.error(f"MQTT Connection Error in /logout (unsubscribe) for user {user_id}: {e}")
    finally:
        logout_user()
        return redirect(url_for('login'))

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
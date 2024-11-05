import os
from datetime import datetime
import time
import paho.mqtt.client as mqtt
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes
# import pyttsx3
from gtts import gTTS
from io import BytesIO
from pydub import AudioSegment
from pydub.playback import play
import pandas as pd
import json
from os.path import exists
import logging
import logging.handlers
from flask import Flask, render_template, request, redirect, url_for, flash, g, abort, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
import requests
import base64
from google.cloud import secretmanager
from forms import ChangePasswordForm
from cryptography.fernet import Fernet
from flask_babel import Babel, gettext as _
from configs.languages import supported_languages
from urllib.parse import urlsplit
from functools import wraps

app = Flask(__name__)
app.secret_key = '1QrightS3cr3tKey'  # Secret key for session management
app.config.from_pyfile('config.py')
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
babel = Babel(app)
#@babel.localeselector

def get_locale():
    return request.accept_languages.best_match(['en', 'es', 'de'])

    #if g.lang_code:
    #    return g.lang_code
    #else:
    #    return "en"

babel.init_app(app, locale_selector=get_locale)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(Exception)
def handle_error(e):
    if (str(e) == '504'):
        session['authentication_status'] = False
        flash(_('Session has expired, please login again'), 'error')
        return redirect(url_for("/login"))


# LOGGING Setup
#log_filename = "IQRight_FE_WEB.debug"
#max_log_size = 20 * 1024 * 1024  # 20Mb
#backup_count = 10
#log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#debug = True
#handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=max_log_size, backupCount=backup_count)

#handler.setFormatter(log_formatter)
#logging.getLogger().addHandler(handler)
#logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)

lastCommand = None

df = pd.read_csv('./full_load.csv',
                 dtype={'ChildID': int, 'IDUser': int, 'FirstName': str, 'LastName': str, 'AppIDApprovalStatus': int \
                     , 'AppApprovalStatus': str, 'DeviceID': str, 'Phone': str, 'ChildName': str, 'ExternalNumber': str \
                     , 'HierarchyLevel1': str, 'HierarchyLevel1Type': str, 'HierarchyLevel1Desc': str \
                     , 'HierarchyLevel2': str, 'HierarchyLevel2Type': str, 'HierarchyLevel2Desc': str \
                     , 'StartDate': str, 'ExpireDate': str, 'IDApprovalStatus': int, 'ApprovalStatus': str
                     , 'MainContact': int, 'Relationship': str})


def connect():
    broker = '127.0.0.1'  # eg. choosen-name-xxxx.cedalo.cloud
    myport = 1883
    client.connect(broker,
                   port=myport,
                   keepalive=60);


#Function to retrieve secrets from Google Cloud Secret Manager, inputs are secret and expect value and output is the secret
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

def api_request(method, url, data, content: bool = False):
    url = app.config['API_URL'] + url + "/"
    headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
        "caller": "LocalApp"
    }

    apiUsername = get_secret('apiUsername')
    apiPassword = get_secret('apiPassword')

    auth = (apiUsername["value"], apiPassword["value"])

    try:
        if method.upper() == 'POST':
            response = requests.post(url=url, auth=auth, headers=headers, data=json.dumps(data))
        else:
            response = requests.get(url=url, headers=headers, data=data)
        if response.status_code == 200:
            if content:
                return 200, response.content
            else:
                return 200, response.json()
        else:
            return response.status_code, {"message": response.text}
    except requests.exceptions.RequestException as e:
        logging.debug('Message Received')(f"Error connecting to the backend service: {e}")
        return 500, {"message": str(e)}

def authenticate_user(username, password):
    payload = {
        'Username': username,
        'Password': password,
        'showDependents': False
    }
    errorMsg = None

    returnCode, info = api_request(method="POST", url='apiGetSession', data=payload)

    if info['message']:
        if returnCode == 200:
            current_user.class_codes = [int(x['IDHierarchy']) for x in info['listHierarchy'] if x['IDHierarchyType'] == 1]
            # Validate if the Login matches the facility'
            facilities = [x['idFacility'] for x in info['listFacilities']]
            if int(IDFACILITY) in facilities:
                teacher = info.get('firstName', '') + ' ' + info.get('lastName', '')
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
            errorMsg = info['message']
    else:
        errorMsg = 'Unexpected Service Return: ' + json.dumps(info)
    if errorMsg:
        return {'authenticated': False, 'classCodes': [], 'errorMsg': info['message'], 'changePassword': False, 'newUser': False}
    else:
        return {'authenticated': True, 'classCodes': current_user.class_codes, 'errorMsg': None, 'changePassword': info.get('changePassword', False), 'newUser': info.get('newUser', False)}


version = '5'  # or '3'
mytransport = 'tcp'  # 'websockets' # or 'tcp'

client = mqtt.Client(client_id="IQRight_Main", transport=mytransport, protocol=mqtt.MQTTv5)
client.username_pw_set("IQRight", "123456")

broker = 'localhost'  # eg. choosen-name-xxxx.cedalo.cloud
myport = 1883
properties = Properties(PacketTypes.CONNECT)
properties.SessionExpiryInterval = 30 * 60  # in seconds

memoryData = {"list1": []}
currList = 1
gridList = 1
loadGrid = 1

IDFACILITY = os.getenv("FACILITY", 0)

def playSoundList(listObj, currGrid, fillGrid: bool = False):
    for jsonObj in listObj:
        externalNumber = jsonObj['externalNumber']
        label_call.config(text=f"{jsonObj['name']} - {jsonObj['level1']}")
        currGrid.insert_row([jsonObj['name'], jsonObj['level1'], jsonObj['level2']], redraw=True)
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
            label_call.flash(0)
        if fillGrid:  # IF FILLING THE WHOLE GRID, SLEEP 2 SECONDS BEFORE PLAYING THE NEXT ONE
            time.sleep(2)


# def on_messageScreen(client, userdata, message, tmp=None):
#     global currGrid
#     global memoryData
#     global currList
#     global debug
#     global gridList
#     global loadGrid
#     global lastCommand
#     if debug:
#         logging.debug('Message Received')
#         logging.debug(str(message.payload, 'UTF-8'))
#         bleMsg = str(message.payload, 'UTF-8')
#         jsonObj = loadJson(str(message.payload, 'UTF-8'))
#         if isinstance(jsonObj, dict):
#             if 'command' in jsonObj:
#                 if lastCommand != jsonObj['command']:
#                     lastCommand = jsonObj['command']
#                     if jsonObj['command'] == 'break':
#                         if gridList == 1:
#                             currGrid = sheet2
#                             gridList = 2
#                         currList += 1
#                         memoryData[f"list{currList}"] = []
#                         print(f'currGrid = sheet2 \ currList = {currList} \ griList = {gridList}')
#                     elif jsonObj['command'] == 'release':
#                         # move grid 2 to grid 1
#                         sheet1.column_width(0, 400)
#                         sheet1.column_width(1, 250)
#                         sheet1.column_width(2, 250)
#                         sheet1.set_sheet_data(sheet2.get_sheet_data(), redraw=True, reset_col_positions=False)
#                         # empty grid 2
#                         sheet2.delete_rows([x for x in range(0, currGrid.get_total_rows())], redraw=True)
#                         loadGrid += 1
#                         secondGrid = loadGrid + 1
#                         if currList >= secondGrid:
#                             sheet2.set_sheet_data(
#                                 [[x['name'], x['level1'], x['level2']] for x in memoryData[f"list{secondGrid}"]],
#                                 redraw=True)
#                             sheet2.column_width(0, 400)
#                             sheet2.column_width(1, 250)
#                             sheet2.column_width(2, 250)
#                             if secondGrid > 2:  # MEANS THERE WAS NOT AUDIO FOR THESE STUDENT
#                                 playSoundList(listObj=memoryData[f"list{secondGrid}"], currGrid=currGrid, fillGrid=True)
#                         if loadGrid == currList:  # MEANS THE LAST LIST IS CURRENT
#                             currGrid = sheet1
#                             gridList = 1
#                 return True
#         else:
#             # GOT A LORA MESSAGE INSERTED INTO THE QUEUE
#             bleMsgLst = bleMsg.split('|')
#             userInfo = getInfo(deviceID=f'{bleMsgLst[0]}{bleMsgLst[2]}', beacon=bleMsgLst[1], distance=bleMsgLst[3])
#             if userInfo:
#                 jsonObj = userInfo
#             else:
#                 jsonObj = {}
#                 return None
#         externalNumber = f"{jsonObj['externalNumber']}"
#         memoryData[f"list{currList}"].append(jsonObj)
#         if currList < (loadGrid + 2):
#             playSoundList([jsonObj], currGrid=currGrid)


def getInfo(beacon, distance, code: str = None, deviceID: str = None):
    global df
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

def encrypt_file(datafile, filename, data):
    """Encrypts a Pandas DataFrame and saves it to a file.

    Args:
        filename: The name of the file to save the encrypted data to.
        data: The Pandas DataFrame to encrypt.
    """
    # Generate a new encryption key
    key = Fernet.generate_key()

    # Create a Fernet object with the encryption key
    f = Fernet(key)

    # Convert the DataFrame to a CSV string
    csv_string = data.to_csv(index=False)

    # Encrypt the CSV string
    encrypted_data = f.encrypt(csv_string.encode())

    # Save the encryption key to a separate file
    with open(filename + '.key', 'wb') as key_file:
        key_file.write(key)

    # Save the encrypted data to the specified file
    with open(datafile, 'wb') as encrypted_file:
        encrypted_file.write(encrypted_data)

    return True

def decrypt_file(datafile, filename):
    """Decrypts a file containing an encrypted Pandas DataFrame.

    Args:
        filename: The name of the file containing the encryption key.
        datafile: The name of the file containing the encrypted data.

    Returns:
        A Pandas DataFrame containing the decrypted data.
    """
    # Read the encryption key from the key file
    with open(filename, 'rb') as key_file:
        key = key_file.read()

    # Create a Fernet object with the encryption key
    f = Fernet(key)

    # Read the encrypted data from the file
    with open(datafile, 'rb') as encrypted_file:
        encrypted_data = encrypted_file.read()

    # Decrypt the data
    decrypted_data = f.decrypt(encrypted_data)

    # Convert the decrypted CSV string to a Pandas DataFrame
    df = pd.read_csv(BytesIO(decrypted_data))

    return df


# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Mock backend authentication service URL (replace with actual URL)

AUTH_SERVICE_URL = get_secret('authServiceUrl')

# User class (for Flask-Login)
class User(UserMixin):
    def __init__(self, id, class_codes):
        self.id = id
        self.class_codes = class_codes

# User loader function for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User(user_id, class_codes=[]) #current_user.class_codes)

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
            user = User(username, response['classCodes'])
            login_user(user, duration = 600)
            session['_newUser'] = response.get('newUser')
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
    return render_template('index.html', class_codes=[])

# Route for logging out
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
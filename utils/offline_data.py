import os
import logging
from datetime import datetime, timedelta
import pandas as pd
from io import StringIO
from cryptography.fernet import Fernet
from pandas.core.interchange.dataframe_protocol import DataFrame
from config import LORASERVICE_PATH, IDFACILITY
from utils.api_client import api_request

class OfflineData:
    _offlineAPIToken: str
    _offlineAPITokenExp: datetime
    _offlineUsersDF: DataFrame
    _allUsersDF: DataFrame
    offlineUserAvailable: bool
    filepath: str

    def __init__(self):
        self._offlineAPIToken: str = ""
        self._offlineAPITokenExp = datetime.now() - timedelta(hours=2)
        self.offlineUserAvailable = False
        self._allUsersDF = self.loadAppUsers()
        self.filepath = LORASERVICE_PATH + '/'

    def encrypt_file(self, datafile, filename, data):
        """Encrypts a Pandas DataFrame and saves it to a file."""
        key = Fernet.generate_key()
        f = Fernet(key)
        csv_string = data.to_csv(index=False)
        encrypted_data = f.encrypt(csv_string.encode())
        
        with open(filename + '.key', 'wb') as key_file:
            key_file.write(key)
        with open(datafile, 'wb') as encrypted_file:
            encrypted_file.write(encrypted_data)
        return True

    def decrypt_file(self, datafile, filename: str ='offline.key'):
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
        except Exception as read_error:
            logging.error(f"Error reading the encrypted file: {read_error}")
            return None

    def openFile(self, filename, keyfilename: str = None):
        """Opens and decrypts a file."""
        keyfilename = self.filepath + keyfilename if keyfilename else None
        if os.path.exists(filename):
            if keyfilename:
                return True, self.decrypt_file(datafile=filename, filename=keyfilename)
            else:
                return True, self.decrypt_file(datafile=filename)
        else:
            logging.critical("No local CSV file found. Terminating.")
            return False, None

    def getToken(self, api_request_func):
        """Gets API token using the provided api_request function."""
        if self._offlineAPITokenExp < datetime.now():
            status_code, response_content = api_request_func(
                method="POST",
                url='apiGetToken/',
                data={"idUser": "localuser", "password": "Lalala1234", "idFacility": 1}
            )
            if status_code == 200:
                self._offlineAPIToken = response_content['token']
                self._offlineAPITokenExp = datetime.fromisoformat(response_content['expiration'].replace("Z", "+00:00"))
                return self._offlineAPIToken
            else:
                return None
        else:
            return self._offlineAPIToken

    def download_and_read_csv(self, url: str, filename: str, api_request_func):
        """Downloads and reads CSV file using the provided api_request function."""
        try:
            filename = self.filepath + filename
            token = self.getToken(api_request_func)
            if token:
                status_code, response_content = api_request_func(
                    method="GET",
                    url=f'{url}/download',
                    data={'idFacility': os.getenv('FACILITY'), 'searchType': 'ALL'},
                    bearer=token
                )
                if status_code == 200:
                    if os.path.exists(f"{filename}.iqr"):
                        try:
                            os.replace(f"{filename}.iqr", f"{filename}.bak")
                        except OSError as e:
                            logging.error(f"Error renaming existing file: {e}")
                            os.replace(f"{filename}.iqr", f"{filename}.bak.error")

                    with open(f"{filename}.iqr", 'wb') as encrypted_file:
                        encrypted_file.write(response_content)
                else:
                    logging.error(f"Error downloading CSV. Status: {status_code}")
                    if response_content.get('message'):
                        logging.error(f"API Error: {response_content.get('message')}")
                    return None
            else:
                logging.error(f"Failed to retrieve Offline Token")

        except Exception as e:
            logging.error(f"Download API request error: {e}")

        return self.openFile(filename=f"{filename}.iqr")

    def getOfflineUsers(self, api_request_func):
        """Gets offline users data."""
        if not self.offlineUserAvailable:
            self.offlineUserAvailable, self._offlineUsersDF = self.download_and_read_csv(
                url="apiGetLocalOfflineUserFile",
                filename="offline_users",
                api_request_func=api_request_func
            )
        return self._offlineUsersDF

    def findUser(self, userName, api_request_func):
        """Finds user in offline data."""
        userDF = self.getOfflineUsers(api_request_func)
        if self.offlineUserAvailable:
            matches = userDF[userDF['UserId'] == userName]
            if not matches.empty:
                info = matches.iloc[0].to_dict()
                info['listFacilities'] = [{'idFacility': int(IDFACILITY)}]
                info['listHierarchy'] = [{'IDHierarchy': str(x)} for x in str(info['IDHierarchy']).split('|')]
                info['fullName'] = info.get('firstName', '') + ' ' + info.get('lastName', '')
                info['roles'] = info['Role']
                return info
        return None

    def loadAppUsers(self):
        """Loads all app users from local file."""
        status, df = self.openFile(filename=f"{self.filepath}full_load.iqr")
        if not status:
            logging.error("UNABLE TO OPEN USER FILE, EXITING")
            exit(1)
        return df

    def getAppUsers(self):
        """Returns all app users."""
        return self._allUsersDF
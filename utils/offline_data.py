import os
import logging
import logging.handlers
from datetime import datetime, timedelta
import pandas as pd
from io import StringIO
from cryptography.fernet import Fernet
from pandas.core.interchange.dataframe_protocol import DataFrame
from utils.config import LORASERVICE_PATH, IDFACILITY
from utils.api_client import api_request

# Set up logging configuration
log_filename = "IQRight_FE_WEB.debug"
max_log_size = 20 * 1024 * 1024  # 20Mb
backup_count = 10
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=max_log_size, backupCount=backup_count)
handler.setFormatter(log_formatter)
logging.getLogger().addHandler(handler)

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
        self.filepath = LORASERVICE_PATH + '/'
        self._allUsersDF = self.loadAppUsers()


    def encrypt_file(self, datafile, filename, data):
        """Encrypts a Pandas DataFrame and saves it to a file."""
        try:
            key = Fernet.generate_key()
            f = Fernet(key)
            csv_string = data.to_csv(index=False)
            encrypted_data = f.encrypt(csv_string.encode())
            
            with open(filename + '.key', 'wb') as key_file:
                key_file.write(key)
            with open(datafile, 'wb') as encrypted_file:
                encrypted_file.write(encrypted_data)
            return True
        except Exception as e:
            logging.error(f"Error encrypting file {filename}: {str(e)}")
            return False

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
        except FileNotFoundError as e:
            logging.error(f"File not found error: {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Error decrypting file {datafile}: {str(e)}")
            return None

    def openFile(self, filename, keyfilename: str = None):
        """Opens and decrypts a file."""
        try:
            keyfilename = self.filepath + keyfilename if keyfilename else None
            if os.path.exists(filename):
                if keyfilename:
                    return True, self.decrypt_file(datafile=filename, filename=keyfilename)
                else:
                    return True, self.decrypt_file(datafile=filename)
            else:
                logging.critical(f"No local CSV file found at {filename}. Terminating.")
                return False, None
        except Exception as e:
            logging.error(f"Error opening file {filename}: {str(e)}")
            return False, None

    def getToken(self):
        """Gets API token using the provided api_request function."""
        try:
            if self._offlineAPITokenExp < datetime.now():
                status_code, response_content = api_request(
                    method="POST",
                    url='apiGetToken/',
                    data={"idUser": "localuser", "password": "Lalala1234", "idFacility": 1}
                )
                if status_code == 200:
                    self._offlineAPIToken = response_content['token']
                    self._offlineAPITokenExp = datetime.fromisoformat(response_content['expiration'].replace("Z", "+00:00"))
                    return self._offlineAPIToken
                else:
                    logging.error(f"Failed to get token. Status code: {status_code}")
                    return None
            else:
                return self._offlineAPIToken
        except Exception as e:
            logging.error(f"Error getting token: {str(e)}")
            return None

    def download_and_read_csv(self, url: str, filename: str):
        """Downloads and reads CSV file using the provided api_request function."""
        try:
            filename = self.filepath + filename
            token = self.getToken()
            if token:
                status_code, response_content = api_request(
                    method="GET",
                    url=f'{url}/download',
                    data={'idFacility': IDFACILITY, 'searchType': 'ALL'},
                    bearer=token
                )
                if status_code == 200:
                    if os.path.exists(f"{filename}.iqr"):
                        try:
                            os.replace(f"{filename}.iqr", f"{filename}.bak")
                        except OSError as e:
                            logging.error(f"Error renaming existing file: {str(e)}")
                            os.replace(f"{filename}.iqr", f"{filename}.bak.error")

                    with open(f"{filename}.iqr", 'wb') as encrypted_file:
                        encrypted_file.write(response_content)
                else:
                    logging.error(f"Error downloading CSV. Status: {status_code}")
                    if response_content.get('message'):
                        logging.error(f"API Error: {response_content.get('message')}")
                    return None
            else:
                logging.error("Failed to retrieve Offline Token")

        except Exception as e:
            logging.error(f"Error downloading and reading CSV: {str(e)}")
            return False, None

        return self.openFile(filename=f"{filename}.iqr")

    def getOfflineUsers(self):
        """Gets offline users data."""
        try:
            if not self.offlineUserAvailable:
                self.offlineUserAvailable, self._offlineUsersDF = self.download_and_read_csv(
                    url="apiGetLocalOfflineUserFile",
                    filename="offline_users")
            return self._offlineUsersDF
        except Exception as e:
            logging.error(f"Error getting offline users: {str(e)}")
            return None

    def findUser(self, userName):
        """Finds user in offline data."""
        try:
            userDF = self.getOfflineUsers()
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
        except Exception as e:
            logging.error(f"Error finding user {userName}: {str(e)}")
            return None

    def loadAppUsers(self):
        """Try to loads all app users from local file."""
        try:
            if os.path.exists(f"{self.filepath}full_load.iqr"):
                status, df = self.openFile(filename=f"{self.filepath}full_load.iqr")
            else:
                status, df = self.download_and_read_csv(url="apiGetLocalUserFile", filename="full_load")
                
            if status == False:
                logging.error("UNABLE TO OPEN USER FILE, EXITING")
                exit(1)
            else:
                return df
        except Exception as e:
            logging.error(f"Error loading app users: {str(e)}")
            exit(1)

    def getAppUsers(self):
        """Returns all app users."""
        try:
            return self._allUsersDF
        except Exception as e:
            logging.error(f"Error getting app users: {str(e)}")
            return None
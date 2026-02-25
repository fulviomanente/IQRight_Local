import os
import logging
import logging.handlers
from datetime import datetime, timedelta
import pandas as pd
from io import StringIO
from cryptography.fernet import Fernet
from numpy.f2py.cfuncs import needs
from pandas.core.interchange.dataframe_protocol import DataFrame
from utils.config import LORASERVICE_PATH, IDFACILITY, OFFLINE_USERS_FILENAME, OFFLINE_FULL_LOAD_FILENAME, LOCAL_FILE_VERSIONS
from utils.api_client import api_request, get_secret
import json
from pathlib import Path

class OfflineData:
    _offlineAPIToken: str
    _offlineAPITokenExp: datetime
    _offlineUsersDF: DataFrame
    _allUsersDF: DataFrame
    _localFileVersions: dict
    offlineUserAvailable: bool
    filepath: str

    def __init__(self):
        self._offlineAPIToken: str = ""
        self._offlineAPITokenExp = datetime.now() - timedelta(hours=2)
        self.offlineUserAvailable = False

        self._basepath = Path(LORASERVICE_PATH)
        self._filepath = self._basepath / 'data'
        self.offline_filename = self._filepath / OFFLINE_FULL_LOAD_FILENAME
        self.offline_user_filename = self._filepath / OFFLINE_USERS_FILENAME

        self._local_file_versions = self._filepath / LOCAL_FILE_VERSIONS
        self._emptyVersions = {OFFLINE_FULL_LOAD_FILENAME: {'version': 'new'}, OFFLINE_USERS_FILENAME: {'version': 'new'}}
        self._localFileVersions = self._load_file_versions()
        self._allUsersDF = self.loadAppUsers()

    def _load_file_versions(self) -> dict:
        """Loads the stored file versions from local JSON."""
        try:
            if os.path.exists(self._local_file_versions):
                with open(self._local_file_versions, 'r') as f:
                    return json.load(f)
            return self._emptyVersions
        except Exception as e:
            logging.error(f"Error loading file versions for {self._local_file_versions}: {str(e)}")
            return self._emptyVersions

    def _save_file_versions(self, filename: str, version_data: dict):
        """Saves the current file versions to local JSON."""
        try:
            search_filename = Path(filename).name
            self._localFileVersions[search_filename] = version_data
            with open(self._local_file_versions, 'w') as f:
                json.dump(self._localFileVersions, f)
        except Exception as e:
            logging.error(f"Error saving file versions for {filename}: {str(e)}")

    def check_file_version(self, filename: str):
        """
        Checks if a new version of the file is available.
        Returns True if new version is available, False otherwise.
        Returns the current version if no new version is available.
        If there is an error, returns True and 0 as version so the process can continue.
        """
        try:
            filename = Path(filename).name
            status_code, response = api_request(
                method="POST",
                url='apiGetFileVersion',
                data={'filename': filename})

            logging.error("called apigetFileVersion")

            if status_code != 200:
                logging.error(f"--Error checking file version: {response.get('message')}")
                return False, 0
    
            version_data = self._localFileVersions.get(filename, self._emptyVersions.get(filename))
            current_version = version_data.get('version', '0.0.0')
            new_version = response.get('latest', '0.0.0')

            if new_version != current_version:
                logging.info(f"New version available for {filename}: {new_version}")
                return True, new_version
            
            logging.debug(f"File {filename} is up to date (version {current_version})")
            return False, current_version   

        except Exception as e:
            logging.error(f"2 Error checking file version for {filename}: {str(e)}")
            return False, 0

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
            key_filename = self._filepath / filename
            with open(key_filename, 'rb') as key_file:
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
            if keyfilename:
                keyfilename = self._filepath / keyfilename
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
                offline_user = get_secret('offlineIdUser')
                offline_pass = get_secret('offlinePassword')
                status_code, response_content = api_request(
                    method="POST",
                    url='apiGetToken/',
                    data={"idUser": offline_user["value"], "password": offline_pass["value"], "idFacility": IDFACILITY}
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

    def download_and_read_csv(self, url: str, filename: str, fileVersion: str = None):
        """Downloads and reads CSV file using the provided api_request function."""
        try:
            if fileVersion == None:
                # Check if we need to download a new version
                needNewFile, fileVersion = self.check_file_version(filename)
            else:
                needNewFile = True
            if not needNewFile:
                if fileVersion != 'new':
                    logging.info(f"Using cached version of {filename} (version {fileVersion})")
                else:
                    logging.info(f"Failed to access getFileVersion! Using cached version of {filename}")
                return self.openFile(filename=filename)

            token = self.getToken()
            if token:
                status_code, response_content = api_request(
                    method="GET",
                    url=f'{url}/download',
                    data={'idFacility': IDFACILITY, 'searchType': 'ALL'},
                    bearer=token
                )
                if status_code == 200:
                    if os.path.exists(filename):
                        try:
                            os.replace(filename, f"{filename}.bak")
                        except OSError as e:
                            logging.error(f"Error renaming existing file: {str(e)}")
                            os.replace(filename, f"{filename}.bak.error")

                    with open(filename, 'wb') as encrypted_file:
                        encrypted_file.write(response_content)

                    #Once the file is downloaded, save the version
                    self._save_file_versions(filename, {'version': fileVersion})
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

        return self.openFile(filename=filename)

    def getOfflineUsers(self):
        """Gets offline users data."""
        try:
            if not self.offlineUserAvailable:
                self.offlineUserAvailable, self._offlineUsersDF = self.download_and_read_csv(
                    url="apiGetLocalOfflineUserFile",
                    filename=self.offline_user_filename)
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

            needNewFile, fileVersion = self.check_file_version(self.offline_filename)
            if needNewFile:
                status, df = self.download_and_read_csv(url="apiGetLocalUserFile", filename=self.offline_filename, fileVersion=fileVersion)
            else:
                if fileVersion != 'new':
                    logging.info(f"Using cached version of {self.offline_filename} (version {fileVersion})")
                else:
                    logging.info(f"Failed to access getFileVersion! Using cached version of {self.offline_filename}")

                if os.path.exists(self.offline_filename):
                    status, df = self.openFile(filename=self.offline_filename)
                else:
                    logging.error("UNABLE TO OPEN USER FILE, EXITING")
                    exit(1)
                
            if status == False:
                logging.error("UNABLE TO OPEN USER FILE, EXITING")
                exit(1)
            else:
                #Convert ExternalNumber to string for search
                df['ExternalNumber'] = df['ExternalNumber'].astype(str)
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
import os
import hashlib
import logging
import logging.handlers
import threading
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
        self._password_cache_file = self._filepath / 'password_cache.json'
        self._emptyVersions = {OFFLINE_FULL_LOAD_FILENAME: {'version': 'new'}, OFFLINE_USERS_FILENAME: {'version': 'new'}}
        self._localFileVersions = self._load_file_versions()
        self._allUsersDF = self.loadAppUsers()
        self.getOfflineUsers()
        self._refresh_timer = None

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

    def _hash_password(self, password: str, salt: str) -> str:
        """Create a SHA-256 hash of the password with a user-specific salt."""
        return hashlib.sha256(f"{salt}:{password}".encode('utf-8')).hexdigest()

    def _load_password_cache(self) -> dict:
        """Load the local password cache from disk."""
        try:
            if os.path.exists(self._password_cache_file):
                with open(self._password_cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Error loading password cache: {str(e)}")
        return {}

    def _save_password_cache(self, cache: dict):
        """Save the local password cache to disk."""
        try:
            with open(self._password_cache_file, 'w') as f:
                json.dump(cache, f)
        except Exception as e:
            logging.error(f"Error saving password cache: {str(e)}")

    def cache_user_password(self, userName: str, password: str):
        """Cache a password hash after successful online authentication."""
        try:
            cache = self._load_password_cache()
            cache[userName] = self._hash_password(password, userName)
            self._save_password_cache(cache)
            logging.debug(f"Cached password for offline login: {userName}")
        except Exception as e:
            logging.error(f"Error caching password for {userName}: {str(e)}")

    def validate_cached_password(self, userName: str, password: str) -> bool:
        """Validate a password against the locally cached hash."""
        cache = self._load_password_cache()
        if userName not in cache:
            logging.warning(f"No cached password for {userName} — user has never logged in online")
            return False
        return cache[userName] == self._hash_password(password, userName)

    def findUser(self, userName, password: str = None):
        """Finds user in offline data and validates password against cached hash."""
        try:
            userDF = self.getOfflineUsers()
            if self.offlineUserAvailable:
                matches = userDF[userDF['UserId'] == userName]
                if not matches.empty:
                    info = matches.iloc[0].to_dict()

                    # Validate password against locally cached hash
                    if password is not None:
                        if not self.validate_cached_password(userName, password):
                            return None

                    info['listFacilities'] = [{'idFacility': int(IDFACILITY)}]
                    info['listHierarchy'] = [{'IDHierarchy': str(x)} for x in str(info['IDHierarchy']).split('|')]
                    info['fullName'] = info.get('FirstName', '') + ' ' + info.get('LastName', '')
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

    def refreshAllData(self):
        """
        Check versions and re-download both data files if newer versions exist.
        Reloads the in-memory DataFrames on success.
        If download fails or the new file is empty, keeps using the previous data.
        """
        logging.info("[REFRESH] Starting scheduled data refresh...")

        # --- Refresh full_load.iqr (app users / student data) ---
        try:
            needNew, fileVersion = self.check_file_version(self.offline_filename)
            if needNew:
                logging.info(f"[REFRESH] New version available for {OFFLINE_FULL_LOAD_FILENAME}: {fileVersion}")
                result = self.download_and_read_csv(
                    url="apiGetLocalUserFile",
                    filename=self.offline_filename,
                    fileVersion=fileVersion
                )
                if result and result[0] and result[1] is not None and not result[1].empty:
                    new_df = result[1]
                    new_df['ExternalNumber'] = new_df['ExternalNumber'].astype(str)
                    self._allUsersDF = new_df
                    logging.info(f"[REFRESH] {OFFLINE_FULL_LOAD_FILENAME} updated and reloaded ({len(new_df)} records)")
                else:
                    logging.warning(f"[REFRESH] {OFFLINE_FULL_LOAD_FILENAME} download returned empty — keeping previous data")
            else:
                logging.info(f"[REFRESH] {OFFLINE_FULL_LOAD_FILENAME} is up to date (version {fileVersion})")
        except Exception as e:
            logging.error(f"[REFRESH] Error refreshing {OFFLINE_FULL_LOAD_FILENAME}: {str(e)} — keeping previous data")

        # --- Refresh offline_users.iqr ---
        try:
            needNew, fileVersion = self.check_file_version(self.offline_user_filename)
            if needNew:
                logging.info(f"[REFRESH] New version available for {OFFLINE_USERS_FILENAME}: {fileVersion}")
                # Temporarily allow re-download by resetting the flag
                prev_available = self.offlineUserAvailable
                prev_df = self._offlineUsersDF if hasattr(self, '_offlineUsersDF') else None
                self.offlineUserAvailable = False

                result = self.download_and_read_csv(
                    url="apiGetLocalOfflineUserFile",
                    filename=self.offline_user_filename,
                    fileVersion=fileVersion
                )
                if result and result[0] and result[1] is not None and not result[1].empty:
                    self._offlineUsersDF = result[1]
                    self.offlineUserAvailable = True
                    logging.info(f"[REFRESH] {OFFLINE_USERS_FILENAME} updated and reloaded ({len(result[1])} records)")
                else:
                    logging.warning(f"[REFRESH] {OFFLINE_USERS_FILENAME} download returned empty — keeping previous data")
                    self.offlineUserAvailable = prev_available
                    if prev_df is not None:
                        self._offlineUsersDF = prev_df
            else:
                logging.info(f"[REFRESH] {OFFLINE_USERS_FILENAME} is up to date (version {fileVersion})")
        except Exception as e:
            logging.error(f"[REFRESH] Error refreshing {OFFLINE_USERS_FILENAME}: {str(e)} — keeping previous data")

        logging.info("[REFRESH] Scheduled data refresh complete")

    def _schedule_next_refresh(self):
        """Schedule the next refresh at 1:30 PM on the next weekday."""
        now = datetime.now()
        target_time = now.replace(hour=13, minute=30, second=0, microsecond=0)

        # If it's already past 1:30 PM today, schedule for tomorrow
        if now >= target_time:
            target_time += timedelta(days=1)

        # Skip weekends (Saturday=5, Sunday=6)
        while target_time.weekday() >= 5:
            target_time += timedelta(days=1)

        delay_seconds = (target_time - now).total_seconds()
        logging.info(f"[REFRESH] Next scheduled refresh at {target_time.strftime('%Y-%m-%d %H:%M')} ({delay_seconds / 3600:.1f} hours)")

        self._refresh_timer = threading.Timer(delay_seconds, self._run_scheduled_refresh)
        self._refresh_timer.daemon = True
        self._refresh_timer.start()

    def _run_scheduled_refresh(self):
        """Execute the refresh and schedule the next one."""
        try:
            self.refreshAllData()
        except Exception as e:
            logging.error(f"[REFRESH] Unhandled error in scheduled refresh: {str(e)}")
        finally:
            self._schedule_next_refresh()

    def start_scheduled_refresh(self):
        """Start the weekday 1:30 PM refresh schedule."""
        logging.info("[REFRESH] Starting scheduled data refresh (weekdays at 1:30 PM)")
        self._schedule_next_refresh()
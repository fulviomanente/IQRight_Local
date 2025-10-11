import os
import json
import logging
import requests
from google.cloud import secretmanager
from utils.config import API_URL, PROJECT_ID, LORASERVICE_PATH
from cryptography.fernet import Fernet

DATA_PATH = f"{LORASERVICE_PATH}/data"
DEFAULT_CREDENTIALS = f'{DATA_PATH}/credentials.iqr'
DEFAULT_KEY = f'{DATA_PATH}/credentials.key'
#Function to retrieve secrets from Google Cloud Secret Manager, inputs are secret and expect value and output is the secret

def get_from_local(self, secret_name: str):
    try:
        if os.path.exists(DEFAULT_KEY):
            """Get secret from local encrypted storage"""
            with open(DEFAULT_KEY, 'rb') as key_file:
                key = key_file.read()
                fernet = Fernet(key)
                logging.debug("Encryption key loaded successfully")
        else:
            logging.warning(f"Encryption key not found at {DEFAULT_KEY}")
            fernet = None
    except Exception as e:
        logging.error(f"Failed to initialize encryption: {e}")
        fernet = None

    try:
        if not os.path.exists(DEFAULT_CREDENTIALS):
            logging.error(f"Local credentials file not found: {DEFAULT_CREDENTIALS}")
            return None

        with open(DEFAULT_CREDENTIALS, 'rb') as f:
            encrypted_data = f.read()

        decrypted_data = fernet.decrypt(encrypted_data)
        credentials = json.loads(decrypted_data.decode('utf-8'))

        if secret_name in credentials:
            logging.debug(f"Retrieved '{secret_name}' from local encrypted storage")
            return credentials[secret_name]
        else:
            logging.warning(f"Secret '{secret_name}' not found in local storage")
            return None

    except Exception as e:
        logging.error(f"Error reading local secret '{secret_name}': {e}")
        return None

def get_secret(secret, expected: str = None, compare: bool = False):
    secret_name = secret
    secretValue: str = None
    result: bool = False
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
        secretValue = client.access_secret_version(name=name)
        if compare and expected:
            if secret == expected:
                result = True
            else:
                result = False
            secretValue = None
        response = {'value': secretValue.payload.data.decode('UTF-8'), 'result': result}
    except Exception as e:
        logging.debug(f'Error getting secret {secret} from GCP, Trying Locally...')
        logging.debug(str(e))

        # Fallback to local encrypted storage
        local_secret = get_from_local(secret_name)
        if local_secret:
            response = {'value': result, 'result': True}
        else:
            response = {'value': None, 'result': False}
    finally:
        return response

def api_request(method, url, data, content: bool = False, bearer: str = None, is_file: bool = False):
    url = f"{API_URL}{url}"
    if is_file:
        headers = {}
    else:
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "caller": "LocalApp"
        }

    if bearer:
        headers['Authorization'] = f'Bearer {bearer}'
    else:
        apiUsername = get_secret('apiUsername')
        apiPassword = get_secret('apiPassword')
        auth = (apiUsername["value"], apiPassword["value"])

    try:
        if method.upper() == 'POST':
            url = url + "/"
            response = requests.post(url=url, auth=auth, headers=headers, data=json.dumps(data))
        else:
            response = requests.get(url=url, headers=headers, params=data, stream=True)

        if is_file:
            if response.status_code == 200:
                return response.status_code, response.content
            else:
                return response.status_code, None
        else:
            if response.status_code == 200:
                if 'application/octet-stream' in response.headers.get('Content-Type', ''):
                    return 200, response.content
                else:
                    return 200, response.json()
            else:
                return response.status_code, {"message": response.text}
    except requests.exceptions.RequestException as e:
        logging.debug(f"Error connecting to the backend service: {e}")
        return 500, {"message": str(e)}


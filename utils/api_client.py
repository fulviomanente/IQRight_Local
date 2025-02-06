import os
import json
import logging
import requests
from google.cloud import secretmanager

#Function to retrieve secrets from Google Cloud Secret Manager, inputs are secret and expect value and output is the secret

def get_secret(secret, expected: str = None, compare: bool = False):
    project_id = os.getenv('PROJECT_ID')
    secret_name = secret
    secretValue: str = None
    result: bool = False
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        secretValue = client.access_secret_version(name=name)
        if compare and expected:
            if secret == expected:
                result = True
            else:
                result = False
            secretValue = None
    except Exception as e:
        logging.debug(f'Error getting secret {secret} from environment')
        logging.debug(str(e))
    finally:
        response = {'value': secretValue.payload.data.decode('UTF-8'), 'result': result}
    return response

def api_request(method, url, data, content: bool = False, bearer: str = None):
    url = os.getenv('API_URL') + url
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
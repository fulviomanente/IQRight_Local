import os
import json
import logging
import requests
from typing import Optional, Dict, Any, Tuple
from utils.secure_credentials import get_secret
from utils.config import API_URL, PROJECT_ID

# Note: get_secret() is now imported from secure_credentials module
# It provides automatic fallback to encrypted local storage when GCP is unavailable

def api_request(method: str, url: str, data: Dict[str, Any],
                content: bool = False, bearer: Optional[str] = None,
                is_file: bool = False) -> Tuple[int, Any]:
    """
    Make API request with automatic credential fallback

    Args:
        method: HTTP method (GET, POST)
        url: API endpoint path
        data: Request data/params
        content: Return content instead of JSON
        bearer: Bearer token (optional)
        is_file: Whether response is a file

    Returns:
        Tuple of (status_code, response_data)
    """
    url = f"{API_URL}{url}"

    if is_file:
        headers = {}
    else:
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "caller": "LocalApp"
        }

    # Handle authentication
    auth = None
    if bearer:
        headers['Authorization'] = f'Bearer {bearer}'
    else:
        # Get credentials with automatic GCP/local fallback
        api_username_result = get_secret('apiUsername')
        api_password_result = get_secret('apiPassword')

        if api_username_result and api_password_result:
            auth = (api_username_result["value"], api_password_result["value"])
        else:
            logging.error("Failed to retrieve API credentials from GCP or local storage")
            return 500, {"message": "Authentication credentials not available"}

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


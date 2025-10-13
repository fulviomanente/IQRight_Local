#!/usr/bin/env python3
import asyncio
import aiohttp
from aiohttp import BasicAuth
import logging
from utils.api_client import get_secret
from utils.config import API_URL, API_TIMEOUT, IDFACILITY

logging.basicConfig(level=logging.INFO)

async def test_api():
    api_url = f"{API_URL}apiGetUserInfo"
    payload = {"searchCode": "TEST123"}  # Replace with a valid test code
    headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
        "caller": "LocalApp",
        "idFacility": str(IDFACILITY)
    }
    
    print(f"Testing API endpoint: {api_url}")
    print(f"Payload: {payload}")
    print(f"Headers: {headers}")
    print(f"Timeout: {API_TIMEOUT} seconds")
    
    apiUsername = get_secret('apiUsername')
    apiPassword = get_secret('apiPassword')
    
    if not apiUsername or not apiPassword:
        print("ERROR: Could not retrieve API credentials from secrets")
        return
    
    print(f"Username: {apiUsername['value']}")
    
    auth = BasicAuth(apiUsername["value"], apiPassword["value"])
    
    # Test with different timeout values
    for timeout in [5, 10, 30]:
        print(f"\n--- Testing with {timeout}s timeout ---")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, timeout=timeout, headers=headers, auth=auth) as response:
                    print(f"Success! Status: {response.status}")
                    data = await response.json()
                    print(f"Response: {data}")
                    break
        except asyncio.TimeoutError:
            print(f"Timeout after {timeout} seconds")
        except aiohttp.ClientError as e:
            print(f"Client error: {e}")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            break

if __name__ == "__main__":
    asyncio.run(test_api())
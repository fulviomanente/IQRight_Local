# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.


## Overview and Project Structure

The project is meant to be deployed on Raspberry Pis and is split in two parts:

### The Server

The server hosts 2 different applications, a local Web Front end that is used by teachers in the classroom to visualize 
the list of kids that are ready to leave and hear their names. Except for the login and choosing the watcher kid 
(which is only informative) there is no interaction with this page. And the second is a local service that is responsible for 
communicating with other devices, sending and receiving information and running business rules.

#### Local Wed Front End

- The local web server running mqtt_grid_web.py as follows:
- The project is a Flask application meant to be deployed Locally.
- Isolation of the users is important and the integration with Paho MQTT is fundamental.
- Every user has a unique ID and a name and the login is done with user and password
- The project is a web application with microservices architecture.
- The project is a Flask-RESTful API.
- The project does not use a database, all the data is stored in the local file system.
- The project uses the Paho MQTT client library for communication with the MQTT broker.
- The project uses the Google Cloud Secret Manager client library for managing the secrets.
- The project uses the Pandas library for data manipulation and analysis.
- The web app MUST allow audio output
- The web app uses SocketIO for communication with the local server and refresh the info in real time
- The web app should have a nice UI/UX and be as simple as possible
- The web app basically have only one page, all the others are related to user authentication and authorization
- The web app should have a nice error handling
- The web add should be able to be fully functional even if the server has lost communication with the internet
- All files stored locally MUST be encrypted
- All parameters for logging in, keys, secrets and anything that should be stored locally should be encrypted 

#### The Meshstatic interface service

- The service is a python script(capture_lora.py) that runs  as follows:
- The service captures the data from the Radio module using meshstatic libraries and send it to the specific MQTT topic
- The service is responsible applying business rules and enriching it with the data from the local files
- The data that is coming is from the Clients (scanners or Bluetooth Modules) is the information of the detection 
- of the parents' presence of a pickup car line in the parking lot
- The service uses the Paho MQTT client library for communication with the MQTT broker.
- The service uses the Google Cloud Secret Manager client library for managing the secrets.
- The service uses the Pandas library for data manipulation and analysis.
- The service is a local service and it is not accessible from the web app
- The service should have no outside communication or dependency what so ever, except the radio to capture the info


## Build & Run Commands
- Run Web App: `flask run` or `python -m flask run` (uses mqtt_grid_web.py)
- Run LoRa Integration: `python CaptureLora.py`
- Create New Key: `python create_key.py`
- Test Adding Messages to Queue: `./load_queue.sh` or `./release_queue.sh`

## Code Style Guidelines and Key Principles 

### Key Principles 
- Python 3 with Flask and MQTT
- Functional, declarative programming; avoid classes except for Flask views
- Use type hints for all function signatures
- Lowercase with underscores for directories and files
- Early returns for error conditions (if-return pattern over nested if-else)
- Descriptive variable names with auxiliary verbs (is_active, has_permission)
- Error handling with try/except at start of functions
- JSON deserialization wrapped in exception handling
- Use defensive coding (None checks, type checks) 
- Secrets managed via Google Cloud Secret Manager
- Config values from environment variables or config.py
- Log errors with stack traces for debugging (debug vs info level)
- Write concise, technical responses with accurate Python examples. 
- Prefer iteration and modularization over code duplication. 
- Use descriptive variable names with auxiliary verbs (e.g., is_active, has_permission). 
- Use lowercase with underscores for directories and files (e.g., blueprints/user_routes.py). 
- Favor named exports for routes and utility functions. 
- Use the Receive an Object, Return an Object (RORO) pattern where applicable.  Python/Flask 
- Use type hints for all function signatures where possible. 
- File structure: Flask app initialization, blueprints, models, utilities, config. 
- Avoid unnecessary curly braces in conditional statements. 
- For single-line statements in conditionals, omit curly braces. 

### Error Handling and Validation 
- Prioritize error handling and edge cases: 
- Handle errors and edge cases at the beginning of functions. 
- Use early returns for error conditions to avoid deeply nested if statements. 
- Place the happy path first in the function for improved readability. 
- Avoid unnecessary else statements; use the if-return pattern instead. 
- Use guard clauses to handle preconditions and invalid states early. 
- Implement proper error logging and user-friendly error messages. 
- Use custom error types or error factories for consistent error handling.  

### Dependencies 
- Flask 
- Flask-JWT-Extended (for JWT authentication)  
- Google Cloud Secret Manager client library (for secret management)
- Paho-MQTT client library (for MQTT communication)
- Pandas (for data manipulation and analysis)
- Meshstatic (for communication)
- Pytest (for testing)
- Pytest-cov (for test coverage)
- Pytest-mock (for mocking)
- Pytest-asyncio (for async testing)

### Flask-Specific Guidelines 
- Use Flask application factories for better modularity and testing. 
- Organize routes using Flask Blueprints for better code organization. 
- Implement custom error handlers for different types of exceptions. 
- Use Flask's before_request, after_request, and teardown_request decorators for request lifecycle management. 
- Use Flask-JWT-Extended for handling authentication and authorization if needed.  
- Use Pandas to handle offline data processing and data manipulation.
- All data processing should be done offline and the results should be saved to a file.
- All files stored locally should be encrypted at rest.


### Key Conventions
 1. Use Flask's application context and request context appropriately. 
 2. Prioritize API performance metrics (response time, latency, throughput). 
 3. Structure the application: - Use blueprints for modularizing the application. 
    - Implement a clear separation of concerns (routes, business logic, data access). 
    - Use environment variables for configuration management.  
    - Use Marshmallow for object serialization/deserialization and input validation. 
    - Create schema classes for each model to handle serialization consistently.  
4. Secrets are stored in Google Cloud Secret Manager and are loaded into the application using the Secret Manager client library.
    
### Integration 
- All services used in the Local Application are part of another project which you have full access to on ../../api_integration_layer 
- Use secure calls for all htts requests sending the proper authentication header
- For file download/upload use the createToken service before calling the main service

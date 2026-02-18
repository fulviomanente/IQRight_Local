# IQRight API Integration Layer - Complete Reference

> **Purpose**: This document is the authoritative reference for Claude Code to understand and correctly call all IQRight API services. It documents authentication, request/response schemas, and usage patterns.

---

## Global Rules and Conventions

### Base URL
```
{BASE_URL}/api/{serviceName}/
```
All APIs are mounted under the `/api/` prefix via a Flask Blueprint.

### Authentication

There are **two authentication mechanisms** used across the APIs:

#### 1. HTTP Basic Auth (`@protected` decorator) - Used by most endpoints

All endpoints decorated with `@protected` require:

- **Authorization Header**: HTTP Basic Auth with the API service account credentials (NOT end-user credentials).
  - Username: stored in DB Parameter table as `api-authentication-user`
  - Password: stored in DB Parameter table as `api-authentication-pwd` (hashed, verified via PBKDF2-SHA512)
- **`caller` Header** (required): Identifies the calling application. Known values:
  - `AdminApp` - Admin web interface
  - `UserApp` - Mobile user app
  - `LocalApp` - Local/on-premise application
  - Any other string is accepted but logged as the caller
- **`idFacility` Header** (optional): Facility ID, used by some services
- **`listFacilities` Header** (optional): Comma-separated list of facility IDs

```python
# Python example - Basic Auth API call
import requests
from requests.auth import HTTPBasicAuth

response = requests.post(
    f"{BASE_URL}/api/apiGetSession/",
    auth=HTTPBasicAuth(API_USERNAME, API_PASSWORD),
    headers={"caller": "AdminApp"},
    json={"Username": "user@example.com", "Password": "userpassword"}
)
```

```bash
# curl example
curl -X POST "{BASE_URL}/api/apiGetSession/" \
  -u "api_user:api_password" \
  -H "Content-Type: application/json" \
  -H "caller: AdminApp" \
  -d '{"Username": "user@example.com", "Password": "userpassword"}'
```

#### 2. JWT Bearer Token (`@token_required` decorator) - Used by download/GET endpoints

Some GET endpoints use JWT Bearer token authentication:
- First obtain a token via `apiGetToken`
- Then pass it as: `Authorization: Bearer <token>`
- Token expires in 24 hours
- Requires user to have `SystemUser` role

```python
# Step 1: Get token
token_response = requests.post(
    f"{BASE_URL}/api/apiGetToken/",
    auth=HTTPBasicAuth(API_USERNAME, API_PASSWORD),
    headers={"caller": "LocalApp"},
    json={"idUser": "system@example.com", "password": "pass", "idFacility": 1}
)
token = token_response.json()["token"]

# Step 2: Use token for GET requests
response = requests.get(
    f"{BASE_URL}/api/apiGetLocalUserFile/download?idFacility=1&searchType=ALL",
    headers={"Authorization": f"Bearer {token}", "caller": "LocalApp"}
)
```

### Standard Error Response Format
All error responses follow this structure:
```json
{
    "message": "Human-readable error description",
    "code": "Error code string",
    "result": "Additional context or the original request content"
}
```

### Common Error Codes
| Code | HTTP Status | Meaning |
|------|-------------|---------|
| 01   | 430         | Invalid API Call - idUser not found or no permission |
| 02   | 430         | idFacility is a mandatory field |
| 03   | 232         | User has no access to this idFacility |
| 04   | 430         | Missing required search fields |
| 05   | 430         | Mandatory field missing |
| 07   | 430         | Password doesn't meet requirements (8+ chars, upper+lower+number) |
| 08   | 430         | IDFacility is mandatory |
| 11   | 233         | Session expired |
| 12   | 430         | Database/processing error |
| 21   | varies      | No records found or permission denied |

### Password Requirements
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number

---

## API Services

---

### 1. apiGetSession (Login)

**URL**: `POST /api/apiGetSession/`
**Auth**: Basic Auth (`@protected`)
**Description**: Primary login endpoint. Authenticates an end-user and returns session info, facilities, dependents, and access tokens.

#### Request Body
```json
{
    "Username": "person@domain.com",
    "Password": "mypassword",
    "showDependents": false,
    "showHierarchy": false,
    "qrCode": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Username | string | Yes | User email |
| Password | string | Yes | User password |
| showDependents | boolean | No | Include dependents list in response |
| showHierarchy | boolean | No | Include hierarchy list in response |
| qrCode | boolean | No | Generate QR code (only for UserApp caller) |

#### Success Response (200)
```json
{
    "message": "User Logged in",
    "userID": 123,
    "fullName": "John Doe",
    "firstName": "John",
    "lastName": "Doe",
    "userName": "john@example.com",
    "phoneNumber": "+1234567890",
    "listFacilities": [
        {"idFacility": 1, "facilityName": "School A", "zoneID": 1, "timezone": -5, "idFacilityGroup": 1}
    ],
    "roles": "{\"Admin\": true, \"readOnly\": false}",
    "access": [{"code": "All", "access": "SuperUser"}],
    "tokenSesionExpiration": "2024-01-01T00:00:00",
    "atkn": "session-token-uuid",
    "changePassword": false,
    "listDependents": [],
    "listHierarchy": [],
    "homeSetup": [],
    "deviceID": "ABC123",
    "qrCode": "base64-encoded-image",
    "newUser": false
}
```

#### Error Responses
| HTTP Code | Meaning |
|-----------|---------|
| 231 | User not found |
| 232 | Invalid password / Account blocked / Password expired |
| 430 | Missing Username or Password |

#### Special Behavior
- **LocalApp caller**: If user is not found, attempts to auto-create a teacher record from the Hierarchy table
- **Password expiry**: Passwords expire after 90 days
- **Account lockout**: After max login attempts, account is blocked
- **QR Code**: Only generated when `caller=UserApp` and `qrCode=true`; returned as base64-encoded PNG

---

### 2. apiGetFacilities

**URL**: `POST /api/apiGetFacilities/`
**Auth**: Basic Auth (`@protected`)
**Description**: Login endpoint that validates credentials and returns facility access information. Similar to apiGetSession but with a simpler response focused on facilities.

#### Request Body
```json
{
    "Username": "person@domain.com",
    "Password": "mypassword",
    "IDFacility": "1"
}
```

#### Success Response (200)
```json
{
    "message": "User Logged in",
    "userID": 123,
    "userName": "John Doe",
    "atkn": "session-token",
    "OTP": null
}
```

---

### 3. apiGetToken

**URL**: `POST /api/apiGetToken/`
**Auth**: Basic Auth (`@protected`)
**Description**: Generates a JWT Bearer token for use with token-authenticated endpoints. The user must have the `SystemUser` role.

#### Request Body
```json
{
    "idUser": "system@domain.com",
    "password": "mypassword",
    "idFacility": 1
}
```

#### Success Response (200)
```json
{
    "idUser": "system@domain.com",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expiration": "2024-01-02T12:00:00"
}
```

#### Notes
- Token is valid for 24 hours
- Uses HS256 algorithm with a secret key stored in Google Secret Manager
- Required for GET endpoints on apiGetLocalUserFile, apiGetLocalOfflineUserFile, and apiGetGenerateQRCode

---

### 4. apiGetUserInfo

**URL**: `POST /api/apiGetUserInfo/`
**Auth**: Basic Auth (`@protected`)
**Description**: Retrieves detailed information about a specific user. Search by ID, username, email, phone, or searchCode.

#### Request Body
```json
{
    "idUser": 123,
    "userName": "",
    "email": "",
    "phone": "",
    "searchCode": "",
    "showFacilities": false,
    "showDependents": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| idUser | integer | One of these is required | Internal user ID |
| userName | string | One of these is required | Username/email |
| email | string | One of these is required | Email address |
| phone | string | One of these is required | Phone number |
| searchCode | string | One of these is required | Device ID or external number |
| showFacilities | boolean | No | Include facilities list |
| showDependents | boolean | No | Include dependents list |

#### Success Response (200)
```json
{
    "message": "API call Successfull",
    "userID": 123,
    "fullName": "John Doe",
    "firstName": "John",
    "lastName": "Doe",
    "userName": "john@example.com",
    "email": "john@example.com",
    "role": "{\"Admin\": false}",
    "changePassword": false,
    "tokenSesionExpiration": "2024-01-01T00:00:00",
    "atkn": "token",
    "inactive": false,
    "phoneNumber": "+1234567890",
    "deviceID": "ABC123",
    "listFacilities": [],
    "listDependents": []
}
```

---

### 5. apiGetUserInfoSummary

**URL**: `POST /api/apiGetUserInfoSummary/`
**Auth**: Basic Auth (`@protected`)
**Description**: Gets summarized user information for physical access scenarios. Searches by device ID or external number within a facility.

#### Request Body
```json
{
    "searchCode": "DEVICE123",
    "idFacility": 1
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| searchCode | string | Yes | Device ID or External Number |
| idFacility | integer | Yes | Facility ID to search in |

#### Success Response (200)
```json
{
    "parentName": "Jane Doe",
    "relationship": "Mother",
    "mainContact": true,
    "userList": [
        {
            "name": "John Doe Jr",
            "hierarchyLevel2": "Grade 3A",
            "hierarchyID": "05",
            "externalID": "DEVICE123",
            "externalNumber": "EXT001",
            "timestamp": "2024-01-15 10:30:00"
        }
    ]
}
```

---

### 6. apiGetUserAccessInfo

**URL**: `POST /api/apiGetUserAccessInfo/`
**Auth**: Basic Auth (`@protected`)
**Description**: Gets resumed access info about a user and their dependents. Supports search by user ID, username, or device ID (searchCode).

#### Request Headers (additional)
- `idFacility`: Facility ID (used when searching by searchCode)

#### Request Body
```json
{
    "idUser": 123,
    "userName": "",
    "searchCode": ""
}
```

#### Success Response (200)
```json
{
    "message": "API call Successfull",
    "userID": 123,
    "fullName": "John Doe",
    "deviceID": "ABC123",
    "listDependents": [
        {
            "idUser": 456,
            "firstName": "Junior",
            "lastName": "Doe",
            "hierarchyLevel2": "Grade 3",
            "hierarchyLevel2Type": "Teacher",
            "approvalStatus": "Approved",
            "approvalStatusExpirationDate": null,
            "idHierarchy": 10
        }
    ]
}
```

---

### 7. apiGetUserList

**URL**: `POST /api/apiGetUserList/`
**Auth**: Basic Auth (`@protected`)
**Description**: Search for users with various filter criteria. Returns a list with user info, parent info, and approval status.

#### Request Body
```json
{
    "hierarchyLevel1": "",
    "hierarchyLevel2": "",
    "firstName": "",
    "lastName": "",
    "parentLastName": "",
    "phoneNumber": "",
    "externalNumber": "",
    "idUser": 0,
    "idFacility": 1,
    "searchType": "Student"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| idFacility | integer | Yes | Facility to search in |
| searchType | string | No | `Student` (default) or `Family` |
| Other fields | various | No | Filter criteria |

#### Success Response (200)
```json
{
    "message": "API call Successfull",
    "userList": [
        {
            "userID": 123,
            "firstName": "John",
            "lastName": "Doe",
            "hierarchyLevel1": "Grade 5",
            "hierarchyLevel2": "Mrs. Smith",
            "externalNumber": "EXT001",
            "parentFirstName": "Jane",
            "parentLastName": "Doe",
            "email": "jane@example.com",
            "phoneNumber": "+1234567890",
            "idApprovalStatus": 2,
            "approvalStatus": "Approved",
            "expireDate": "2024-12-31",
            "relationship": "Mother",
            "parentID": 456,
            "mainContact": true
        }
    ]
}
```

---

### 8. apiGetAdminUserList

**URL**: `POST /api/apiGetAdminUserList/`
**Auth**: Basic Auth (`@protected`)
**Description**: Gets a list of admin/super users. Can filter by name, external number, or user type.

#### Request Body
```json
{
    "firstName": "",
    "lastName": "",
    "externalNumber": "",
    "idUser": 0,
    "idFacility": 1,
    "searchType": "All"
}
```

| Field | Type | Description |
|-------|------|-------------|
| searchType | string | `All`, `SuperUser`, or `Admin` |
| idFacility | integer | Facility to search in |

#### Success Response (200)
```json
{
    "message": "API call Successfull",
    "userList": [
        {
            "userID": 1,
            "firstName": "Admin",
            "lastName": "User",
            "externalNumber": "ADM001",
            "email": "admin@example.com",
            "phoneNumber": "+1234567890",
            "adminUser": "true",
            "superUser": "true"
        }
    ]
}
```

---

### 9. apiGetUserHierarchy

**URL**: `POST /api/apiGetUserHierarchy/`
**Auth**: Basic Auth (`@protected`)
**Description**: Gets users related to a given user ID, either up (parents) or down (children) the hierarchy.

#### Request Body
```json
{
    "idAdminUser": 1,
    "idUser": 123,
    "idFacility": 1,
    "searchType": "parent"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| idAdminUser | integer | Yes | ID of the admin user making the request |
| idUser | integer | Yes | User ID to search relationships for |
| idFacility | integer | Yes | Facility ID |
| searchType | string | No | `parent` (default) or `child` |

#### Success Response (200)
```json
{
    "message": "Success",
    "idUser": 123,
    "userList": [
        {
            "idUser": 456,
            "firstName": "Jane",
            "lastName": "Doe",
            "email": "jane@example.com",
            "phoneNumber": "+1234567890",
            "idApprovalStatus": 2,
            "approvalStatus": "Approved",
            "expireDate": "2024-12-31",
            "relationship": "Mother",
            "mainContact": true,
            "canApprove": false,
            "canDeny": false
        }
    ]
}
```

---

### 10. apiGetPendingApprovalList

**URL**: `POST /api/apiGetPendingApprovalList/`
**Auth**: Basic Auth (`@protected`)
**Description**: Gets a list of users pending approval. Requires admin privileges.

#### Request Body
```json
{
    "adminIDUser": 1,
    "idFacility": 1,
    "approvalListType": "Ad-hoc"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| adminIDUser | integer | Yes | Admin user ID performing the query |
| idFacility | integer | Yes | Facility ID (must be > 0) |
| approvalListType | string | Yes | `Ad-hoc` or `Access` |

#### Success Response (200)
```json
{
    "message": "API call Successfull",
    "userList": [
        {
            "userID": 123,
            "fullName": "John Doe",
            "hierarchyLevel1": "Grade 5",
            "hierarchyLevel2": "Mrs. Smith",
            "parentFullName": "Jane Doe",
            "requestorFullName": "Jane Doe",
            "email": "jane@example.com",
            "phoneNumber": "+1234567890",
            "idApprovalStatus": 1,
            "approvalStatus": "Pending",
            "expireDate": null,
            "relationship": "Mother",
            "info": "",
            "requestorUserID": 456
        }
    ]
}
```

---

### 11. apiGetPreApprovedUsers

**URL**: `POST /api/apiGetPreApprovedUsers/`
**Auth**: Basic Auth (`@protected`)
**Description**: Gets all pre-approved users for a facility. The requesting user must have access to the specified facility.

#### Request Body
```json
{
    "idUser": 1,
    "idFacility": 1
}
```

#### Success Response (200)
```json
{
    "message": "Success",
    "listDependents": [
        {
            "FirstName": "John",
            "LastName": "Doe",
            "Grade": "5th",
            "Teacher": "Mrs. Smith",
            "Email": "jane@example.com",
            "ResponsibleFirstName": "Jane",
            "ResponsibleLastName": "Doe",
            "UserType": "Parent"
        }
    ]
}
```

---

### 12. apiGetParamData

**URL**: `POST /api/apiGetParamData/`
**Auth**: Basic Auth (`@protected`)
**Description**: Retrieves parameter/lookup data from the system tables.

#### Request Body
```json
{
    "idFacility": 1,
    "idUser": 123,
    "paramType": "UserType"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| idFacility | integer | Yes | Facility ID (must be > 0) |
| idUser | integer | Yes | User ID for permission validation |
| paramType | string | Yes | One of: `UserType`, `HierarchyType`, `CommentType`, `ApprovalStatus`, `RelationshipType` |

#### Success Response (200)
```json
{
    "idFacility": 1,
    "list": [
        {"idParameter": 1, "code": "01", "description": "Student"},
        {"idParameter": 2, "code": "02", "description": "Parent"}
    ]
}
```

---

### 13. apiGetParamHierarchy

**URL**: `POST /api/apiGetParamHierarchy/`
**Auth**: Basic Auth (`@protected`)
**Description**: Gets hierarchy information (grades, teachers, etc.) for a facility. Use IDHierarchyType 2 for Grades and 1 for Teachers.

#### Request Headers (additional)
- `listFacilities`: Comma-separated list of facility IDs

#### Request Body
```json
{
    "idFacility": 1,
    "facilityName": "",
    "idHierarchyType": 2,
    "idHierarchyParent": 0
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| idFacility | integer | Conditional | Facility ID (or use facilityName) |
| facilityName | string | Conditional | Facility name (alternative to idFacility) |
| idHierarchyType | integer | No | 1=Teachers, 2=Grades |
| idHierarchyParent | integer | No | Filter by parent hierarchy ID |

#### Success Response (200)
```json
{
    "list": [
        {
            "idHierarchy": 1,
            "code": "G5",
            "description": "Fifth Grade",
            "idHierarchyType": 2,
            "idFacility": 1,
            "idHierarchyParent": 0,
            "hierarchyType": "Grade",
            "children": [
                {
                    "idHierarchy": 10,
                    "code": "T1",
                    "description": "Mrs. Smith",
                    "idHierarchyType": 1,
                    "idFacility": 1,
                    "idHierarchyParent": 1,
                    "hierarchyType": "Teacher"
                }
            ]
        }
    ]
}
```

---

### 14. apiGetLocalUserList

**URL**: `POST /api/apiGetLocalUserList/`
**Auth**: Basic Auth (`@protected`)
**Description**: Gets user data formatted for the local/on-premise IQRight server. Supports delta (changed records only) or full data.

#### Request Body
```json
{
    "idUser": 0,
    "idFacility": 1,
    "searchType": "DELTA"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| idFacility | integer | Yes | Facility ID |
| searchType | string | No | `DELTA` (default, only changes), `ALL` or `FULL` (everything) |

#### Success Response (200)
```json
{
    "message": "API call Successfull",
    "userList": [
        {
            "userID": 123,
            "firstName": "John",
            "lastName": "Doe",
            "idApprovalStatusApp": 2,
            "approvalStatusApp": "Approved",
            "phoneNumber": "+1234567890",
            "deviceID": "ABC123",
            "childName": "Junior Doe",
            "externalNumber": "EXT001",
            "hierarchyLevel1Type": "Grade",
            "hierarchyLevel1Desc": "Fifth Grade",
            "hierarchyLevel1": "5",
            "hierarchyLevel2Type": "Teacher",
            "hierarchyLevel2Desc": "Mrs. Smith",
            "hierarchyLevel2": "Smith",
            "expireDate": "2024-12-31",
            "startDate": "2024-01-01",
            "idApprovalStatus": 2,
            "approvalStatus": "Approved",
            "relationship": "Mother",
            "mainContact": true
        }
    ]
}
```

---

### 15. apiGetLocalUserFile

**URL (POST)**: `POST /api/apiGetLocalUserFile/`
**Auth (POST)**: Basic Auth (`@protected`)

**URL (GET)**: `GET /api/apiGetLocalUserFile/download?idFacility=1&searchType=ALL`
**Auth (GET)**: JWT Bearer Token (`@token_required`)

**Description**: Returns an encrypted CSV file with user data for the local IQRight server. The file is encrypted with Fernet (symmetric encryption) using a per-facility key stored in Google Secret Manager.

**Response Type**: Binary file stream (`application/octet-stream`)

#### POST Request Body
```json
{
    "idUser": 0,
    "idFacility": 1,
    "searchType": "DELTA"
}
```

#### GET Query Parameters
| Param | Required | Values |
|-------|----------|--------|
| idFacility | Yes | Facility ID |
| searchType | Yes | `ALL`, `FULL`, or `DELTA` |

#### Response
- Content-Type: `application/octet-stream`
- Returns encrypted CSV file as attachment
- Filename pattern: `{generated_name}.encrypted`

---

### 16. apiGetLocalOfflineUserFile

**URL (POST)**: `POST /api/apiGetLocalOfflineUserFile/`
**Auth (POST)**: Basic Auth (`@protected`)

**URL (GET)**: `GET /api/apiGetLocalOfflineUserFile/download?idFacility=1&searchType=ALL`
**Auth (GET)**: JWT Bearer Token (`@token_required`)

**Description**: Similar to apiGetLocalUserFile but generates offline login data. Returns an encrypted CSV file.

**Response Type**: Binary file stream (`application/octet-stream`)

#### Request/Response: Same structure as apiGetLocalUserFile

---

### 17. apiGetGenerateQRCode

**URL (POST)**: `POST /api/apiGetGenerateQRCode/`
**Auth (POST)**: Basic Auth (`@protected`)

**URL (GET)**: `GET /api/apiGetGenerateQRCode/download?idFacility=1&searchType=INPUT&searchValue=ABC123`
**Auth (GET)**: No auth required (public GET endpoint)

**Description**: Generates QR codes based on search criteria or input values. Can return as image, base64 string, or Google Storage URL.

#### POST Request Body
```json
{
    "idUser": 123,
    "idFacility": 1,
    "searchType": "INPUT",
    "searchValue": "ABC123",
    "returnType": "IMAGE"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| idFacility | integer | No | Facility ID |
| idUser | integer | No | User ID to generate QR for |
| searchType | string | No | `INPUT` (default), `IDUSER`, or `NUMBER` |
| searchValue | string | No | Value to encode in QR or search term |
| returnType | string | No | `IMAGE` (default, returns PNG), `BASE64`, or `URL` |

#### Success Response
- **returnType=IMAGE** (200): PNG image stream (`image/png`)
- **returnType=BASE64** (200): `{"base64": "base64-encoded-png-string"}`
- **returnType=URL** (200): `{"url": "https://storage.googleapis.com/..."}`

---

### 18. apiGetDataCSV

**URL**: `POST /api/apiGetDataCSV/`
**Auth**: Basic Auth (`@protected`)
**Description**: Export data in CSV format. Requires user with `Admin`, `SuperUser`, and `DownloadData` roles.

#### Request Body
```json
{
    "action": "FullExport",
    "idUser": 1,
    "idFacility": 1,
    "returnURL": true,
    "start_date": "2024-01-01 00:00:00",
    "end_date": "2024-12-31 23:59:59",
    "filter": [],
    "sendEmail": false,
    "emailDestinationList": []
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| action | string | Yes | `FullExport` or `Delta` |
| idUser | integer | Yes | User ID (must have download permissions) |
| idFacility | integer | Yes | Facility ID |
| returnURL | boolean | No | If true, returns a URL to the file; otherwise returns hash |
| start_date | string | No | Start date filter (YYYY-MM-DD HH:MM:SS) |
| end_date | string | No | End date filter |
| sendEmail | boolean | No | Send download link via email |
| emailDestinationList | list[string] | No | Email recipients |

#### Success Response (200)
```json
{
    "csvURL": "https://storage.googleapis.com/...",
    "csvhash": "hash-of-csv-content",
    "emailSent": false
}
```

---

### 19. apiGetFileVersion

**URL**: `POST /api/apiGetFileVersion/`
**Auth**: Basic Auth (`@protected`)
**Description**: Gets the latest and previous version numbers for a named file.

#### Request Body
```json
{
    "filename": "localapp.apk"
}
```

#### Success Response (200)
```json
{
    "filename": "localapp.apk",
    "latest": "2.1.0",
    "previous": "2.0.5"
}
```

---

### 20. apiGetParentQRData

**URL**: `POST /api/apiGetParentQRDataInfo/`
**Auth**: Basic Auth (`@protected`)
**Description**: Gets parent data with their children for QR code generation, filtered by grades and/or teachers.

#### Request Headers (additional)
- `idFacility`: Facility ID

#### Request Body
```json
{
    "idUser": 0,
    "userName": "",
    "searchCode": {
        "grade": ["Fifth Grade"],
        "teacher": ["Mrs. Smith"]
    },
    "includeSiblings": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| searchCode | object | Yes | Filter criteria |
| searchCode.grade | list[string] | Conditional | Grade names to filter |
| searchCode.teacher | list[string] | Conditional | Teacher names to filter |
| includeSiblings | boolean | No | Include sibling records |

#### Success Response (200)
```json
{
    "parents": [
        {
            "parentID": "DEV123",
            "externalNumber": "DEV123",
            "children": [
                {
                    "firstName": "John",
                    "lastName": "Doe",
                    "grade": "Fifth Grade"
                }
            ]
        }
    ]
}
```

---

### 21. apiUpdateUserRegistration

**URL**: `POST /api/apiUpdateUserRegistration/`
**Auth**: Basic Auth (`@protected`)
**Description**: Registers a new user on the IQRight platform. Behavior differs based on the caller.

#### Request Body
```json
{
    "firstName": "John",
    "lastName": "Doe",
    "userName": "john@example.com",
    "password": "SecurePass1",
    "idFacility": 1,
    "idUser": 0,
    "userAdmin": false,
    "superUser": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| firstName | string | Yes | First name |
| lastName | string | Yes | Last name |
| userName | string | Yes | Email (used as username) |
| password | string | Conditional | Password (auto-generated for AdminApp if blank) |
| idFacility | integer | Yes | Facility ID |
| idUser | integer | Conditional | Admin user ID (required for AdminApp caller to validate permissions) |
| userAdmin | boolean | No | Grant admin access (AdminApp only) |
| superUser | boolean | No | Grant super user access (AdminApp only) |

#### Caller-Specific Behavior
- **UserApp**: Checks PreApprovedUser table, sends OTP via email, sets approval status to Pending
- **AdminApp**: Validates admin permissions, auto-generates password if blank, sends welcome email

#### Success Response (200)
```json
{
    "message": "Success",
    "userID": 789,
    "userName": "john@example.com",
    "atkn": "session-token-uuid",
    "deviceID": "FAC1abcdef"
}
```

---

### 22. apiUpdateUserInfo

**URL**: `POST /api/apiUpdateUserInfo/`
**Auth**: Basic Auth (`@protected`)
**Description**: Updates user information. Only send fields that need to change; blank values will set the DB field to NULL.

#### Request Body
```json
{
    "adminIDUser": 1,
    "idUser": 123,
    "idFacility": 1,
    "firstName": "John",
    "lastName": "Doe",
    "email": "newemail@example.com",
    "phone": "+1234567890",
    "hierarchyLevel1": "5",
    "hierarchyLevel2": "Smith",
    "externalNumber": "EXT001",
    "revokeAccess": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| adminIDUser | integer | Yes | ID of the user performing the change |
| idUser | integer | Yes | ID of the user being updated |
| idFacility | integer | Yes | Facility ID |
| All other fields | various | No | Only include fields to update |

#### Permission Rules
- **AdminApp**: Requires Admin+SuperUser role
- **UserApp**: User can update own record or records where they are MainContact

#### Success Response (200)
```json
{
    "message": "Success",
    "idUser": 123
}
```

---

### 23. apiUpdateUserPassword

**URL**: `POST /api/apiUpdateUserPassword/`
**Auth**: Basic Auth (`@protected`)
**Description**: Changes a user's password. Requires current password verification.

#### Request Body
```json
{
    "userName": "john@example.com",
    "currentPassword": "OldPass1",
    "newPassword": "NewPass2"
}
```

#### Validation Rules
- All three fields are required
- Current password must be correct
- New password must differ from current
- New password must meet requirements (8+ chars, upper+lower+number)

#### Success Response (200)
```json
{
    "message": "Password changed successfully",
    "code": "00"
}
```

---

### 24. apiUpdatePasswordReset

**URL (POST)**: `POST /api/apiUpdatePasswordReset/`
**Auth (POST)**: Basic Auth (`@protected`)

**URL (GET)**: `GET /api/apiUpdatePasswordReset/?userName=john@example.com`
**Auth (GET)**: None (public GET endpoint)

**Description**: Resets a user's password to a random 8-character string and sends it via email.

#### POST Request Body
```json
{
    "userName": "john@example.com"
}
```

#### Success Response (200)
```json
{
    "message": "An email has being sent with your new password",
    "code": "00"
}
```

#### GET Response
Returns a plain text string: `"An email with your new password has been sent to: john@example.com"`

---

### 25. apiUpdateUserOTP

**URL**: `POST /api/apiUpdateUserOTP/`
**Auth**: Basic Auth (`@protected`)
**Description**: Generates a new OTP and sends it to the user's email.

#### Request Body
```json
{
    "idUser": 123,
    "userName": "john@example.com",
    "idFacility": 1
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| idUser | integer | Conditional | User ID (provide this or userName) |
| userName | string | Conditional | Username (provide this or idUser) |
| idFacility | integer | Yes | Facility ID |

#### Success Response (200)
```json
{
    "message": "Success",
    "idUser": 123,
    "tokenSesionExpiration": "2024-01-01T00:00:00",
    "atkn": "session-token"
}
```

---

### 26. apiValidateUserOTP

**URL**: `POST /api/apiValidateUserOTP/`
**Auth**: Basic Auth (`@protected`)
**Description**: Validates an OTP code and returns complete user info on success. Used as the final step of registration/verification flow.

#### Request Body
```json
{
    "idUser": 123,
    "userOTP": "123456",
    "sesionToken": "uuid-session-token"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| idUser | integer | Yes | User ID |
| userOTP | string | Yes | OTP code to validate |
| sesionToken | string | Yes | Session token received during registration |

#### Success Response (200)
Same structure as apiGetSession response (full user info with facilities, dependents, etc.)

#### Error Responses
| HTTP Code | Meaning |
|-----------|---------|
| 232 | User not found |
| 233 | Session expired |
| 430 | Invalid OTP, missing fields, or database error |

---

### 27. apiUpdateUserApproval

**URL**: `POST /api/apiUpdateUserApproval/`
**Auth**: Basic Auth (`@protected`)
**Description**: Approve, deny, or revoke user access or relationships.

#### Request Body
```json
{
    "adminIDUser": 1,
    "idUser": 123,
    "idUserRequestor": 456,
    "idFacility": 1,
    "action": "approve",
    "startingDate": "2024-01-01",
    "expireDate": "2024-12-31"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| adminIDUser | integer | Yes | Admin user performing the action |
| idUser | integer | Yes | User being approved/denied |
| idUserRequestor | integer | Yes | User who requested the relationship |
| idFacility | integer | Yes | Facility ID |
| action | string | Yes | `approve`, `deny`, or `revoke` |
| startingDate | string | No | Start date (YYYY-MM-DD), defaults to today |
| expireDate | string | No | Expiration date (YYYY-MM-DD) |

#### Permission Rules
- **AdminApp**: Requires Admin+SuperUser role
- **UserApp**: Only MainContact of the child can approve

#### Success Response (200)
```json
{
    "message": "Success",
    "idUser": 123,
    "idUserRequestor": 456
}
```

---

### 28. apiUpdateUserRelationship

**URL**: `POST /api/apiUpdateUserRelationship/`
**Auth**: Basic Auth (`@protected`)
**Description**: Creates or links parent-child relationships between users. Can also create new users as part of the process.

#### Request Body
```json
{
    "adminIDUser": 1,
    "justAddRecord": false,
    "childUser": {
        "idUser": 0,
        "firstName": "Junior",
        "lastName": "Doe",
        "hierarchyLevel1": "5",
        "hierarchyLevel2": "Smith",
        "externalNumber": "EXT001"
    },
    "parentUser": {
        "idUser": 0,
        "firstName": "Jane",
        "lastName": "Doe",
        "email": "jane@example.com",
        "phone": "+1234567890",
        "mainContact": true
    },
    "idFacility": 1,
    "startingDate": "2024-01-01",
    "expireDate": "2024-12-31",
    "relationship": "Mother"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| adminIDUser | integer | Yes | Admin user ID |
| justAddRecord | boolean | No | If true, only creates users without linking |
| childUser.idUser | integer | Yes | 0 to create new, >0 for existing |
| parentUser.idUser | integer | Yes | 0 to create new, >0 for existing |
| idFacility | integer | Yes | Facility ID |
| relationship | string | No | Relationship description |
| startingDate | string | No | YYYY-MM-DD format |
| expireDate | string | No | YYYY-MM-DD format |

#### Important Notes
- If `childUser.idUser=0`: Attempts to find by externalNumber or name+hierarchy; creates new if not found
- If `parentUser.idUser=0`: Attempts to find by email or phone; creates new if not found
- New parent users get a random password and welcome email
- Duplicate relationships are rejected

#### Success Response (200)
```json
{
    "message": "Users Successfully Created/Linked",
    "parentIDUser": 456,
    "childIDUser": 123
}
```

---

### 29. apiImpSchoolFile

**URL**: `POST /api/apiImpSchoolFile/`
**Auth**: Basic Auth (`@protected`)
**Description**: Receives a PubSub message containing a path to a pre-formatted CSV file in Google Storage and imports pre-approved school users.

#### Request Body (PubSub format)
```json
{
    "message": {
        "data": "base64-encoded-json-string"
    }
}
```

The base64-decoded `data` field should contain:
```json
{
    "filePath": "2024-01-15_unique-id.csv",
    "idFacility": 1,
    "idUser": 1
}
```

#### Success Response (200)
```json
{
    "message": "Import Process Finished Successfully",
    "code": "00",
    "result": "Success details"
}
```

---

## User Types and Roles

### User Types (IDUserType)
| Code | Description |
|------|-------------|
| 1 | Student/Child |
| 2 | Parent/Guardian |
| 3 | Teacher (internal) |

### Roles (JSON stored in User.Role)
```json
{
    "Admin": false,
    "readOnly": false,
    "SuperUser": false,
    "DownloadData": false,
    "StudentGrid": false,
    "AppUser": false,
    "SystemUser": false
}
```

### Approval Status Codes
| Code | Description | Login Enabled |
|------|-------------|---------------|
| 1 | Pending | No |
| 2 | Approved | Yes |
| 3 | Denied | No |
| 4 | Approved by Parent (pending admin) | Varies |
| 6 | OTP Validated | Yes |
| 7 | Revoked | No |

---

## Common Patterns

### Typical Registration Flow (Mobile App)
1. `POST apiUpdateUserRegistration` - Register user (sends OTP email)
2. `POST apiUpdateUserOTP` - Resend OTP if needed
3. `POST apiValidateUserOTP` - Validate OTP and complete registration
4. `POST apiGetSession` - Login

### Typical Admin Flow
1. `POST apiGetSession` (caller=AdminApp) - Admin login
2. `POST apiGetPendingApprovalList` - Get pending approvals
3. `POST apiUpdateUserApproval` - Approve/deny users
4. `POST apiGetUserList` - Search users
5. `POST apiUpdateUserInfo` - Update user records

### Local Server Sync Flow
1. `POST apiGetToken` - Get JWT token
2. `GET apiGetLocalUserFile/download` - Download encrypted user data
3. `GET apiGetLocalOfflineUserFile/download` - Download offline data
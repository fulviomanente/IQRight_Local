# Secure Credentials Setup Guide

This guide explains how to set up encrypted local credentials for offline operation and automatic fallback when Google Cloud Secret Manager is unavailable.

## Overview

The IQRight Local system uses a dual-credential system:
1. **Primary**: Google Cloud Secret Manager (requires internet)
2. **Fallback**: Encrypted local credential file (offline capable)

When the system cannot reach Google Cloud (no internet, network issues, authentication problems), it automatically falls back to encrypted local credentials.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Credential Flow                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Application Request: get_secret('apiUsername')         │
│         │                                               │
│         ▼                                               │
│  ┌──────────────────────┐                              │
│  │ SecureCredentials    │                              │
│  │ Manager              │                              │
│  └──────┬───────────────┘                              │
│         │                                               │
│         ├──► Try Google Cloud Secret Manager           │
│         │    (primary source)                           │
│         │    ✓ Success → Return value                  │
│         │    ✗ Fail → Continue to fallback             │
│         │                                               │
│         └──► Try Local Encrypted Storage               │
│              (fallback source)                          │
│              ✓ Success → Return value                  │
│              ✗ Fail → Return None                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## File Locations

| File | Purpose | Location |
|------|---------|----------|
| `credentials.key` | Encryption key | `{LORASERVICE_PATH}/data/credentials.key` |
| `credentials.iqr` | Encrypted credentials | `{LORASERVICE_PATH}/data/credentials.iqr` |

**Default Path**:
- Production: `/etc/iqright/LoraService/data/`
- Development: `./data/`

## Initial Setup

### Step 1: Generate Encryption Key

```bash
cd /path/to/IQRight_Local/Meshstatic
python3 utils/credential_setup.py --generate-key
```

**Output:**
```
✓ Encryption key generated: /etc/iqright/LoraService/data/credentials.key
  IMPORTANT: Keep this key secure and backed up!
```

**⚠️ CRITICAL**: Backup this key file! Without it, you cannot decrypt your credentials.

```bash
# Backup the key
sudo cp /etc/iqright/LoraService/data/credentials.key ~/credentials.key.backup
```

### Step 2: Add Credentials

You have two options:

#### Option A: Sync from Google Cloud (Recommended)

If you have internet access and GCP credentials configured:

```bash
python3 utils/credential_setup.py --sync-from-gcp
```

This automatically syncs these secrets from GCP:
- `apiUsername`
- `apiPassword`
- `mqttUsername`
- `mqttPassword`
- `authServiceUrl`

**Output:**
```
Syncing secrets from Google Cloud Project: iqright
  ✓ Synced: apiUsername
  ✓ Synced: apiPassword
  ✓ Synced: mqttUsername
  ✓ Synced: mqttPassword
  ✓ Synced: authServiceUrl

✓ Synced 5/5 secrets from GCP
```

#### Option B: Add Credentials Manually

If you don't have GCP access or want to add credentials manually:

```bash
# Add API credentials
python3 utils/credential_setup.py --add apiUsername
# You'll be prompted to enter the value securely

python3 utils/credential_setup.py --add apiPassword

# Add MQTT credentials
python3 utils/credential_setup.py --add mqttUsername
python3 utils/credential_setup.py --add mqttPassword

# Add auth service URL (optional)
python3 utils/credential_setup.py --add authServiceUrl
```

**Alternatively**, provide the value on command line (less secure - visible in history):
```bash
python3 utils/credential_setup.py --add apiUsername "myusername"
```

### Step 3: Verify Credentials

```bash
python3 utils/credential_setup.py --list
```

**Output:**
```
Stored credentials in /etc/iqright/LoraService/data/credentials.iqr:
  • apiPassword: my_secure_passwor...
  • apiUsername: integration_user
  • authServiceUrl: https://integration...
  • mqttPassword: mqtt_secure_pass...
  • mqttUsername: iqright_mqtt

Total: 5 credentials
```

## Required Credentials

| Credential | Purpose | Example Value |
|-----------|---------|---------------|
| `apiUsername` | API authentication | `integration_user` |
| `apiPassword` | API authentication | `secure_password_123` |
| `mqttUsername` | MQTT broker auth | `iqright_mqtt` |
| `mqttPassword` | MQTT broker auth | `mqtt_pass_456` |
| `authServiceUrl` | Authentication service | `https://auth.iqright.app` |

## Testing Offline Mode

### Test 1: Force Offline Mode

```python
from utils.secure_credentials import get_credentials_manager

manager = get_credentials_manager()

# Force offline mode (disable GCP)
manager.force_offline_mode()

# Test credential retrieval
result = manager.get_secret('apiUsername')
print(f"Username: {result['value']}")  # Should work from local storage
```

### Test 2: Simulate Network Failure

```bash
# Block GCP Secret Manager API
sudo iptables -A OUTPUT -d secretmanager.googleapis.com -j DROP

# Run your application - should fall back to local credentials
python3 CaptureMeshstatic.py

# Restore network
sudo iptables -D OUTPUT -d secretmanager.googleapis.com -j DROP
```

### Test 3: Check Logs

```bash
tail -f log/IQRight_Daemon.debug
```

Look for these messages:

**Online Mode (GCP working):**
```
INFO - Google Cloud Secret Manager client initialized
INFO - Retrieved 'apiUsername' from Google Cloud Secret Manager
```

**Offline Mode (Fallback to local):**
```
WARNING - Could not initialize GCP client: ...
INFO - Operating in OFFLINE mode - using local credentials only
INFO - Retrieved 'apiUsername' from local encrypted storage
```

## Credential Sync Strategy

### Initial Deployment (With Internet)

1. Deploy code to Raspberry Pi
2. Run `--sync-from-gcp` to populate local credentials
3. Application works online with GCP
4. Local credentials ready for offline fallback

### Regular Updates

```bash
# Sync periodically to keep local credentials current
python3 utils/credential_setup.py --sync-from-gcp
```

**Recommended**: Add to cron for automatic sync:
```bash
# Add to /etc/cron.daily/iqright-sync-credentials
#!/bin/bash
cd /home/pi/IQRight_Local/Meshstatic
python3 utils/credential_setup.py --sync-from-gcp >> /var/log/iqright-credential-sync.log 2>&1
```

### Offline-First Deployment (No Internet)

1. On a machine with internet access:
   - Generate key
   - Add credentials manually
2. Copy both files to Raspberry Pi:
   ```bash
   scp data/credentials.key pi@raspberrypi:/etc/iqright/LoraService/data/
   scp data/credentials.iqr pi@raspberrypi:/etc/iqright/LoraService/data/
   ```
3. Set proper permissions:
   ```bash
   sudo chmod 600 /etc/iqright/LoraService/data/credentials.*
   sudo chown pi:pi /etc/iqright/LoraService/data/credentials.*
   ```

## Security Best Practices

### File Permissions

Credentials files should be readable only by the application user:

```bash
# Set correct ownership
sudo chown pi:pi /etc/iqright/LoraService/data/credentials.*

# Restrict permissions (owner read/write only)
sudo chmod 600 /etc/iqright/LoraService/data/credentials.*
```

Verify:
```bash
ls -la /etc/iqright/LoraService/data/
# Should show: -rw------- 1 pi pi ... credentials.key
#              -rw------- 1 pi pi ... credentials.iqr
```

### Key Rotation

To rotate the encryption key:

```bash
# 1. Generate new key to temporary location
python3 utils/credential_setup.py --generate-key --key-path ./new_credentials.key

# 2. Decrypt old credentials (manually or with script)
# 3. Re-encrypt with new key
# 4. Replace old key file
# 5. Restart services
```

### Backup Strategy

**What to backup**:
- `credentials.key` - CRITICAL: Store securely offline
- `credentials.iqr` - Can be regenerated from GCP

**What NOT to backup**:
- Don't store key and credentials together in the same backup

**Example backup script**:
```bash
#!/bin/bash
# Backup encryption key to secure location
KEY_FILE="/etc/iqright/LoraService/data/credentials.key"
BACKUP_DIR="/secure/backup/location"
DATE=$(date +%Y%m%d)

cp $KEY_FILE $BACKUP_DIR/credentials.key.$DATE
gpg --encrypt --recipient admin@yourcompany.com $BACKUP_DIR/credentials.key.$DATE
```

## Troubleshooting

### Issue: "Encryption key not found"

**Symptom:**
```
✗ Encryption key not found: /etc/iqright/LoraService/data/credentials.key
```

**Solution:**
```bash
python3 utils/credential_setup.py --generate-key
```

### Issue: "Failed to retrieve credentials"

**Symptom:**
```
ERROR - Failed to retrieve API credentials from GCP or local storage
```

**Solution:**
1. Check if credentials exist:
   ```bash
   python3 utils/credential_setup.py --list
   ```
2. If empty, add credentials:
   ```bash
   python3 utils/credential_setup.py --sync-from-gcp
   # OR
   python3 utils/credential_setup.py --add apiUsername
   ```

### Issue: "Cannot decrypt credentials"

**Symptom:**
```
ERROR - Error reading local secret: Fernet decryption failed
```

**Possible Causes:**
1. Wrong encryption key
2. Corrupted credentials file
3. File was modified

**Solution:**
```bash
# Re-generate credentials
mv /etc/iqright/LoraService/data/credentials.iqr{,.backup}
python3 utils/credential_setup.py --sync-from-gcp
```

### Issue: Permissions Denied

**Symptom:**
```
PermissionError: [Errno 13] Permission denied: '/etc/iqright/LoraService/data/credentials.key'
```

**Solution:**
```bash
# Fix ownership
sudo chown -R pi:pi /etc/iqright/LoraService/data/

# Fix permissions
chmod 600 /etc/iqright/LoraService/data/credentials.*
```

## Advanced Usage

### Custom Paths

```bash
# Use custom locations
export LORASERVICE_PATH="/custom/path"
python3 utils/credential_setup.py --generate-key

# Or specify explicitly
python3 utils/credential_setup.py \
  --key-path /custom/path/my.key \
  --credentials-path /custom/path/my.iqr \
  --generate-key
```

### Programmatic Access

```python
from utils.secure_credentials import SecureCredentials

# Initialize with custom paths
creds = SecureCredentials(
    project_id='iqright',
    credentials_path='/custom/path/credentials.iqr',
    key_path='/custom/path/credentials.key'
)

# Get secret
result = creds.get_secret('apiUsername')
if result:
    username = result['value']

# Add secret programmatically
creds.set_local_secret('newSecret', 'newValue')

# Check if offline
if creds.is_offline():
    print("Operating in offline mode")

# Sync from GCP
creds.sync_from_gcp(['apiUsername', 'apiPassword'])
```

### Multiple Environments

```bash
# Development
export LORASERVICE_PATH="./dev"
python3 utils/credential_setup.py --add apiUsername "dev_user"

# Production
export LORASERVICE_PATH="/etc/iqright/LoraService"
python3 utils/credential_setup.py --add apiUsername "prod_user"
```

## Migration from Old System

If you're migrating from the old `api_client.get_secret()`:

### Before (Old - GCP Only)
```python
from utils.api_client import get_secret

apiUsername = get_secret('apiUsername')
# Fails if GCP unavailable
```

### After (New - Automatic Fallback)
```python
from utils.secure_credentials import get_secret

apiUsername = get_secret('apiUsername')
# Automatically falls back to local if GCP unavailable
```

**Migration Steps:**
1. Generate encryption key
2. Sync credentials from GCP
3. Code already updated to use `secure_credentials`
4. Test offline mode
5. No code changes needed!

## Deployment Checklist

- [ ] Generate encryption key on server
- [ ] Backup encryption key securely
- [ ] Sync or add all required credentials
- [ ] Verify credentials with `--list`
- [ ] Set correct file permissions (600)
- [ ] Test online mode (GCP access)
- [ ] Test offline mode (disable network)
- [ ] Monitor logs for credential retrieval
- [ ] Document credential locations in runbook
- [ ] Set up periodic sync (cron job)

## Security Considerations

### ✓ DO:
- Keep encryption key separate from credentials file in backups
- Use restrictive file permissions (600)
- Rotate credentials regularly
- Sync from GCP periodically
- Monitor access logs
- Use strong passwords for credential values

### ✗ DON'T:
- Don't commit credentials or keys to git
- Don't store keys in environment variables
- Don't share encryption key via email/chat
- Don't use world-readable permissions
- Don't skip backups of encryption key
- Don't hard-code credentials in application code

## Support

For issues or questions:
1. Check logs: `/var/log/iqright/` and application logs
2. Verify credential setup: `--list`
3. Test credential retrieval in Python console
4. Review this documentation
5. Check file permissions and ownership

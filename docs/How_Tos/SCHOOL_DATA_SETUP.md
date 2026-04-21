# School Data Setup — Scanner Student File

Procedure for generating and deploying the `students.csv` file that powers both scanner **search** and **validation mode**. Perform this once per school during initial setup, and again whenever the student roster changes significantly (new students, teacher reassignments, grade promotions).

---

## Why One File

The scanner does two things that need student data:

| Feature | Consumes | Columns used |
|---|---|---|
| **Search** (fuzzy name lookup) | `data/students.csv` | FirstName, LastName, DeviceID, ClassCode |
| **Validation Mode** (local lookup) | `data/students.csv` | ChildName, DeviceID, HierarchyLevel1, HierarchyLevel2 |

Both features read the **same file**. This guarantees that the validation step is checking against the same data the operator sees during normal scanning — no drift, no stale snapshots, no compatibility surprises between versions.

The authoritative source of truth is `full_load.iqr` (encrypted) on the IQRight API. The extraction script downloads it, decrypts it, and writes a slim 7-column `students.csv` containing only what the scanner needs.

---

## Prerequisites

Run this procedure on a computer that has:

- **Network access** to the IQRight API (`https://integration.iqright.app/api/`)
- **API credentials** encrypted at `data/credentials.iqr` + decryption key at `data/credentials.key`
- **Offline decryption key** at `data/offline.key` (matches the key used by the API to encrypt `full_load.iqr`)
- **Python environment** with the server dependencies installed:
  ```bash
  pip install -r configs/requirements.server.txt
  ```
- **Config file** at `utils/config.py` configured for the target facility (correct `IDFACILITY`)

> The easiest environment to run this in is the **server machine itself** — it already has all credentials, keys, and config in place. Alternatively, you can run it from a developer laptop with the same files copied over.

---

## Procedure

### 1. Generate `students.csv` from the latest API data

From the project root:

```bash
LOCAL=TRUE python utility_tools/extract_students_csv.py
```

What this does:

1. Connects to the IQRight API using credentials from `data/credentials.iqr`
2. Checks for a new version of `full_load.iqr` on the server
3. Downloads the latest version if needed (stores encrypted at `data/full_load.iqr`)
4. Decrypts in memory using `data/offline.key`
5. Extracts the 7 columns listed below
6. Writes `data/students.csv`

**Expected output:**

```
14:32:11 [INFO] Initializing OfflineData (will download if new version available)...
14:32:13 [INFO] New version available for full_load.iqr: 3.2.1
14:32:15 [INFO] Wrote 389 rows to /path/to/data/students.csv
14:32:15 [INFO] Summary: 389 unique DeviceIDs, 18 teachers, 9 grades
```

#### Output columns

| Column | Example | Used by |
|---|---|---|
| `FirstName` | `Anna` | Search (name tokens) |
| `LastName` | `Smith` | Search (name tokens) |
| `ChildName` | `Anna Smith` | Validation (display) |
| `DeviceID` | `P27810777` | Search + Validation (lookup key) |
| `ClassCode` | `4P` | Search (grade display) |
| `HierarchyLevel1` | `Fourth Grade` | Validation (grade display) |
| `HierarchyLevel2` | `Mrs. Patterson` | Validation (teacher display) |

### 2. Verify the CSV

Open the file and sanity-check a few rows:

```bash
head -5 data/students.csv
wc -l data/students.csv     # should be row count + 1 (header)
```

Look for:
- All rows have a DeviceID starting with `P`
- Teacher names look correct (no blanks, no garbage)
- Grade values match what you expect for the current school year

### 3. Transfer to the scanner(s)

The scanners are normally offline, so copy the file via SD card, USB, SCP, or whatever transfer mechanism your deployment uses:

```bash
# Example: SCP to scanner at IP 192.168.1.50
scp data/students.csv iqright@192.168.1.50:/home/iqright/data/students.csv
```

Or, when building a scanner bundle, the file is already included in `data/` and gets packaged automatically.

### 4. Restart the scanner application (optional)

The `scanner_multi.py` application reads `students.csv` lazily:
- **Search** — loaded on first press of the Search button
- **Validation** — loaded on first toggle into Validation mode

If the scanner is running and either feature was already used, restart the service to pick up the new file:

```bash
ssh iqright@<scanner-ip>
sudo systemctl restart iqright-scanner
```

---

## Options

### Re-extract without re-downloading

If you already have a recent `full_load.iqr` and just want to regenerate `students.csv` (e.g., after updating the extract script):

```bash
LOCAL=TRUE python utility_tools/extract_students_csv.py --no-download
```

### Custom output path

```bash
LOCAL=TRUE python utility_tools/extract_students_csv.py --output /tmp/students.csv
```

### Verbose logging

```bash
LOCAL=TRUE python utility_tools/extract_students_csv.py -v
```

---

## Troubleshooting

### "Missing columns in source data"

The `full_load.iqr` returned by the API is missing one of the expected columns. This usually means:

- The API endpoint changed format
- The facility hasn't been fully set up with ClassCode assignments

**Fix:** Check the available columns printed in the error message, then contact the API team or verify that the facility's students have teacher/class assignments.

### "Failed to retrieve Offline Token" / API authentication errors

- Verify `data/credentials.iqr` and `data/credentials.key` exist and are correct for the target facility
- Check network connectivity: `curl https://integration.iqright.app/api/apiGetFileVersion`
- Check the API-side credentials haven't expired

### "Failed to decrypt" / Fernet InvalidToken

- `data/offline.key` doesn't match the key the server used to encrypt `full_load.iqr`
- This usually means the key was re-generated on the server side — request the new key from the backend team

### Paths resolve to `/home/iqright/data`

You forgot to set `LOCAL=TRUE`. The config file defaults to server paths when not in local mode:

```bash
LOCAL=TRUE python utility_tools/extract_students_csv.py
```

### Scanner still shows old data after update

The scanner caches the DataFrame in memory once loaded. Restart the service:

```bash
sudo systemctl restart iqright-scanner
```

---

## Complete New-School Setup Checklist

When onboarding a new school:

1. [ ] Obtain API credentials from the IQRight backend team
2. [ ] Create `data/credentials.iqr` and `data/credentials.key` for the facility
3. [ ] Verify `data/offline.key` matches the server's encryption key
4. [ ] Update `utils/config.py` with the correct `IDFACILITY`
5. [ ] Run `LOCAL=TRUE python utility_tools/extract_students_csv.py`
6. [ ] Inspect `data/students.csv` — verify row count, spot-check teacher/grade values
7. [ ] Transfer `students.csv` to each scanner's `/home/iqright/data/` directory
8. [ ] Restart scanner services: `sudo systemctl restart iqright-scanner`
9. [ ] On each scanner:
   - Press **Search** — verify student list loads, test a name lookup
   - Toggle **VAL mode** — scan a test QR code, verify correct name/grade/teacher shows
10. [ ] Document the extraction date somewhere (e.g., in the deployment checklist) so you know how stale the local copy is

---

## Updating an Existing School

When the roster changes (new enrollments, teacher moves, grade promotions):

1. Run `LOCAL=TRUE python utility_tools/extract_students_csv.py` (downloads new version if available)
2. Transfer updated `students.csv` to each scanner
3. Restart scanner services

The API versions each file, so re-running the script will only download if there's an actual change.

---

## Related Files

| File | Purpose |
|---|---|
| `utility_tools/extract_students_csv.py` | The extraction script |
| `utils/offline_data.py` | Download + decrypt logic (reused by the script) |
| `utils/matching_engine.py` | `StudentMatcher` — consumes `students.csv` for search |
| `scanner_multi.py` | `_lookup_validation_db()` — consumes `students.csv` for validation |
| `data/students.csv` | Generated output — the single source of truth on each scanner |
| `data/full_load.iqr` | Encrypted source (downloaded and kept for reference) |
| `data/offline.key` | Decryption key (same on server and extraction host) |
| `data/credentials.iqr` | Encrypted API credentials |
| `data/credentials.key` | Decryption key for credentials |

# Generate Student Audio Files

This script creates MP3 audio files for student names using Google Text-to-Speech (gTTS). These files are played on the teacher's web interface when a student is called for pickup.

## How It Works

1. Decrypts the student database (`full_load.iqr`) using the encryption key
2. Filters students by grade (configurable)
3. Generates an MP3 file for each student's name via Google TTS
4. Saves files as `./static/sounds/{external_number}.mp3`
5. Skips files that already exist (safe to re-run)

## Prerequisites

```bash
pip install gTTS cryptography pandas
```

An internet connection is required (gTTS calls Google's TTS API).

## Usage

From the project root:

```bash
python utility_tools/generate_audio.py
```

### Custom file paths

```bash
DATA_PATH=./data/full_load.iqr KEY_PATH=./offline.key python utility_tools/generate_audio.py
```

## Changing Target Grades

Edit the `TARGET_GRADES` list in `utility_tools/generate_audio.py`:

```python
# Current configuration
TARGET_GRADES = ['Third Grade', 'Fourth Grade', 'Sixth Grade']
```

Grade values must match exactly what's in the `HierarchyLevel1` column of the student database. Common values:

| Value | Grade |
|---|---|
| `Kindergarten` | Kindergarten |
| `First Grade` | 1st Grade |
| `Second Grade` | 2nd Grade |
| `Third Grade` | 3rd Grade |
| `Fourth Grade` | 4th Grade |
| `Fifth Grade` | 5th Grade |
| `Sixth Grade` | 6th Grade |
| `Seventh Grade` | 7th Grade |
| `Eighth Grade` | 8th Grade |

To generate for all grades, set:

```python
TARGET_GRADES = ['Kindergarten', 'First Grade', 'Second Grade', 'Third Grade',
                 'Fourth Grade', 'Fifth Grade', 'Sixth Grade', 'Seventh Grade', 'Eighth Grade']
```

## Output

Files are saved to `./static/sounds/` with the student's external number as the filename:

```
static/sounds/
├── 10001.mp3
├── 10002.mp3
├── 10003.mp3
└── ...
```

The web interface (`mqtt_grid_web.py`) serves these files via the `/getAudio/{external_number}` endpoint.

## Re-running

The script skips students whose audio file already exists. To regenerate all files, delete the contents of `./static/sounds/` first:

```bash
rm ./static/sounds/*.mp3
python utility_tools/generate_audio.py
```

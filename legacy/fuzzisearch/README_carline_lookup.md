# Carline Student Lookup - Hybrid Voice + Pick List

## Quick Start

```bash
# Install dependencies
pip3 install flask pandas metaphone rapidfuzz

# Optional: PocketSphinx for voice mode
sudo apt install pocketsphinx pocketsphinx-en-us

# Run
python3 app.py --students students.csv --grammar names.gram --dict names.dict --port 5000
```

Open browser on any device on the same network: `http://<pi-ip>:5000`

## How It Works

1. **Voice mode**: Operator taps mic, says a name. PocketSphinx gives its best
   guess (even at 37% accuracy). The matching engine uses phonetic similarity
   (Double Metaphone) + fuzzy string matching (Levenshtein) to find the top 8
   candidate students. Operator taps the correct one.

2. **Type mode**: Real-time fuzzy search as you type 2+ characters. Handles
   misspellings, partial names, nicknames.

3. **First/Last name mode**: Search only by first or last name when the
   operator only knows one.

## Architecture

```
USB Mic → arecord → PocketSphinx → raw text (often wrong)
                                        ↓
                                 Matching Engine
                            (Metaphone + Levenshtein)
                                        ↓
                              Top 8 candidates on screen
                                        ↓
                              Operator taps correct name
```

## Files

- `app.py` — Flask web app (voice + text search UI)
- `matching_engine.py` — Phonetic + fuzzy matching engine
- `names.dict` — PocketSphinx pronunciation dictionary
- `names.gram` — PocketSphinx JSGF grammar
- `generate_pocketsphinx_files.py` — Regenerate dict/gram from CSV

## Dependencies

- **Required**: flask, pandas, metaphone, rapidfuzz
- **Optional** (voice): pocketsphinx, alsa-utils (arecord)

## Integration

The `/api/select` endpoint fires when a student is tapped. Edit the
`api_select()` function in `app.py` to hook into your carline/QR system.

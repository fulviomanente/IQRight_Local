"""
app.py

Carline Student Lookup - Hybrid Voice + Pick List

Flask app that provides:
  1. Voice search: Records audio, runs PocketSphinx, shows phonetic matches
  2. Text search: Real-time fuzzy search as you type
  3. Pick list: Tappable results optimized for touchscreen

Run:
    python3 app.py --students students.csv --port 5000

The voice recording is done server-side using arecord (ALSA).
For Pi Zero with USB mic or I2S MEMS mic.
"""

import os
import sys
import json
import argparse
import subprocess
import tempfile
import wave
from flask import Flask, render_template_string, request, jsonify

from matching_engine import StudentMatcher

app = Flask(__name__)
matcher = None

# ---------------------------------------------------------------------------
# PocketSphinx voice recognition
# ---------------------------------------------------------------------------
GRAMMAR_PATH = None
DICT_PATH = None


def record_audio(duration=3, rate=16000):
    """Record audio from default ALSA capture device."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()

    try:
        subprocess.run(
            [
                "arecord",
                "-f", "S16_LE",
                "-r", str(rate),
                "-c", "1",
                "-d", str(duration),
                "-q",
                tmp.name,
            ],
            check=True,
            timeout=duration + 5,
        )
        return tmp.name
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Recording error: {e}")
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        return None


def recognize_speech(wav_path):
    """
    Run PocketSphinx on a WAV file.
    Returns the recognized text (may be inaccurate - that's expected).
    """
    if not wav_path or not os.path.exists(wav_path):
        return ""

    cmd = ["pocketsphinx_continuous", "-infile", wav_path]

    # Use custom grammar/dict if available
    if GRAMMAR_PATH and os.path.exists(GRAMMAR_PATH):
        cmd.extend(["-jsgf", GRAMMAR_PATH])
    if DICT_PATH and os.path.exists(DICT_PATH):
        cmd.extend(["-dict", DICT_PATH])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # PocketSphinx outputs recognized text to stdout
        # Filter out log messages (they go to stderr)
        text = result.stdout.strip()
        # Clean up: take last non-empty line (result line)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        return lines[-1] if lines else ""
    except Exception as e:
        print(f"Recognition error: {e}")
        return ""
    finally:
        if os.path.exists(wav_path):
            os.unlink(wav_path)


# ---------------------------------------------------------------------------
# HTML Template - Touchscreen optimized
# ---------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>Student Lookup</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');

  * { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #242836;
    --accent: #3b82f6;
    --accent-glow: rgba(59, 130, 246, 0.3);
    --text: #e8eaed;
    --text-dim: #8b8fa3;
    --success: #22c55e;
    --warning: #f59e0b;
    --radius: 12px;
  }

  html, body {
    height: 100%;
    font-family: 'DM Sans', sans-serif;
    background: var(--bg);
    color: var(--text);
    overflow: hidden;
    touch-action: manipulation;
    -webkit-user-select: none;
    user-select: none;
  }

  .container {
    display: flex;
    flex-direction: column;
    height: 100vh;
    max-width: 480px;
    margin: 0 auto;
    padding: 12px;
    gap: 10px;
  }

  /* Header */
  .header {
    text-align: center;
    padding: 6px 0;
  }
  .header h1 {
    font-size: 18px;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: -0.3px;
  }

  /* Search mode tabs */
  .mode-tabs {
    display: flex;
    gap: 6px;
    background: var(--surface);
    padding: 4px;
    border-radius: var(--radius);
  }
  .mode-tab {
    flex: 1;
    padding: 10px 8px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: var(--text-dim);
    font-family: inherit;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }
  .mode-tab.active {
    background: var(--accent);
    color: white;
    box-shadow: 0 2px 12px var(--accent-glow);
  }

  /* Search input area */
  .search-area {
    position: relative;
  }
  .search-input {
    width: 100%;
    padding: 14px 16px;
    padding-right: 50px;
    border: 2px solid var(--surface2);
    border-radius: var(--radius);
    background: var(--surface);
    color: var(--text);
    font-family: inherit;
    font-size: 18px;
    outline: none;
    transition: border-color 0.2s;
  }
  .search-input:focus {
    border-color: var(--accent);
  }
  .search-input::placeholder {
    color: var(--text-dim);
  }
  .clear-btn {
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    width: 34px;
    height: 34px;
    border: none;
    border-radius: 50%;
    background: var(--surface2);
    color: var(--text-dim);
    font-size: 18px;
    cursor: pointer;
    display: none;
  }
  .clear-btn.visible { display: block; }

  /* Voice button */
  .voice-area {
    display: none;
    flex-direction: column;
    align-items: center;
    gap: 10px;
  }
  .voice-area.active { display: flex; }

  .voice-btn {
    width: 100px;
    height: 100px;
    border: none;
    border-radius: 50%;
    background: var(--accent);
    color: white;
    font-size: 40px;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 4px 20px var(--accent-glow);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .voice-btn:active, .voice-btn.recording {
    transform: scale(1.1);
    box-shadow: 0 4px 30px var(--accent-glow);
  }
  .voice-btn.recording {
    background: #ef4444;
    animation: pulse 1s infinite;
  }
  @keyframes pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
    50% { box-shadow: 0 0 0 20px rgba(239, 68, 68, 0); }
  }

  .voice-status {
    font-size: 14px;
    color: var(--text-dim);
    text-align: center;
    min-height: 20px;
  }

  .voice-heard {
    font-size: 13px;
    color: var(--warning);
    background: rgba(245, 158, 11, 0.1);
    padding: 6px 14px;
    border-radius: 20px;
    display: none;
  }
  .voice-heard.visible { display: inline-block; }

  /* Results list */
  .results-area {
    flex: 1;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
  }

  .results-label {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 4px 0 8px;
  }

  .result-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px;
    margin-bottom: 6px;
    background: var(--surface);
    border: 2px solid transparent;
    border-radius: var(--radius);
    cursor: pointer;
    transition: all 0.15s;
    -webkit-tap-highlight-color: transparent;
  }
  .result-item:active {
    background: var(--surface2);
    border-color: var(--accent);
    transform: scale(0.98);
  }
  .result-name {
    font-size: 18px;
    font-weight: 500;
  }
  .result-score {
    font-size: 12px;
    color: var(--text-dim);
    background: var(--surface2);
    padding: 4px 10px;
    border-radius: 20px;
    min-width: 42px;
    text-align: center;
  }
  .result-score.high { color: var(--success); background: rgba(34, 197, 94, 0.1); }
  .result-score.mid { color: var(--warning); background: rgba(245, 158, 11, 0.1); }

  .no-results {
    text-align: center;
    color: var(--text-dim);
    padding: 40px 20px;
    font-size: 15px;
  }

  /* Selected confirmation */
  .selected-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(15, 17, 23, 0.95);
    z-index: 100;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 20px;
  }
  .selected-overlay.visible {
    display: flex;
  }
  .selected-name {
    font-size: 28px;
    font-weight: 700;
    color: var(--success);
  }
  .selected-check {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    background: rgba(34, 197, 94, 0.15);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 40px;
  }
  .dismiss-btn {
    padding: 14px 40px;
    border: 2px solid var(--surface2);
    border-radius: var(--radius);
    background: transparent;
    color: var(--text);
    font-family: inherit;
    font-size: 16px;
    cursor: pointer;
    margin-top: 20px;
  }

  /* Text area hidden by default */
  .text-area { display: none; }
  .text-area.active { display: block; }

  /* Duration selector for voice */
  .duration-row {
    display: flex;
    gap: 6px;
    justify-content: center;
  }
  .dur-btn {
    padding: 6px 14px;
    border: 1px solid var(--surface2);
    border-radius: 20px;
    background: transparent;
    color: var(--text-dim);
    font-family: inherit;
    font-size: 13px;
    cursor: pointer;
  }
  .dur-btn.active {
    border-color: var(--accent);
    color: var(--accent);
  }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>&#x1F50D; Student Lookup</h1>
  </div>

  <!-- Mode tabs -->
  <div class="mode-tabs">
    <button class="mode-tab active" onclick="setMode('voice')" id="tab-voice">&#x1F3A4; Voice</button>
    <button class="mode-tab" onclick="setMode('text')" id="tab-text">&#x2328; Type</button>
    <button class="mode-tab" onclick="setMode('first')" id="tab-first">First Name</button>
    <button class="mode-tab" onclick="setMode('last')" id="tab-last">Last Name</button>
  </div>

  <!-- Voice search -->
  <div class="voice-area active" id="voice-area">
    <div class="duration-row">
      <button class="dur-btn" onclick="setDuration(2)">2s</button>
      <button class="dur-btn active" onclick="setDuration(3)" id="dur-3">3s</button>
      <button class="dur-btn" onclick="setDuration(5)">5s</button>
    </div>
    <button class="voice-btn" id="voice-btn" onclick="startVoice()">&#x1F3A4;</button>
    <div class="voice-status" id="voice-status">Tap and say the LAST NAME</div>
    <span class="voice-heard" id="voice-heard"></span>
  </div>

  <!-- Text search -->
  <div class="text-area" id="text-area">
    <div class="search-area">
      <input class="search-input" type="text" id="search-input"
             placeholder="Type name..." autocomplete="off" autocorrect="off"
             autocapitalize="off" spellcheck="false">
      <button class="clear-btn" id="clear-btn" onclick="clearSearch()">&times;</button>
    </div>
  </div>

  <!-- Results -->
  <div class="results-area" id="results-area">
    <div class="no-results" id="no-results">
      Speak or type a student name to search
    </div>
    <div id="results-list"></div>
  </div>
</div>

<!-- Selection confirmation overlay -->
<div class="selected-overlay" id="selected-overlay">
  <div class="selected-check">&#x2713;</div>
  <div class="selected-name" id="selected-name"></div>
  <button class="dismiss-btn" onclick="dismissSelection()">OK — Back to Search</button>
</div>

<script>
  let currentMode = 'voice';
  let recordDuration = 3;
  let isRecording = false;
  let searchTimeout = null;

  // ------- Mode switching -------
  function setMode(mode) {
    currentMode = mode;
    document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));

    if (mode === 'voice') {
      document.getElementById('tab-voice').classList.add('active');
      document.getElementById('voice-area').classList.add('active');
      document.getElementById('text-area').classList.remove('active');
    } else {
      document.getElementById('voice-area').classList.remove('active');
      document.getElementById('text-area').classList.add('active');

      if (mode === 'text') {
        document.getElementById('tab-text').classList.add('active');
        document.getElementById('search-input').placeholder = 'Type full or partial name...';
      } else if (mode === 'first') {
        document.getElementById('tab-first').classList.add('active');
        document.getElementById('search-input').placeholder = 'Type first name...';
      } else {
        document.getElementById('tab-last').classList.add('active');
        document.getElementById('search-input').placeholder = 'Type last name...';
      }

      clearSearch();
      document.getElementById('search-input').focus();
    }
  }

  // ------- Duration selector -------
  function setDuration(d) {
    recordDuration = d;
    document.querySelectorAll('.dur-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
  }

  // ------- Voice recording -------
  async function startVoice() {
    if (isRecording) return;
    isRecording = true;

    const btn = document.getElementById('voice-btn');
    const status = document.getElementById('voice-status');
    const heard = document.getElementById('voice-heard');

    btn.classList.add('recording');
    btn.innerHTML = '&#x23F9;';
    status.textContent = `Listening for ${recordDuration}s...`;
    heard.classList.remove('visible');

    try {
      const resp = await fetch('/api/voice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duration: recordDuration })
      });
      const data = await resp.json();

      if (data.error) {
        status.textContent = 'Error: ' + data.error;
      } else {
        const raw = data.heard || '(nothing)';
        heard.textContent = 'Heard: "' + raw + '"';
        heard.classList.add('visible');
        status.textContent = data.results.length + ' matches found';
        renderResults(data.results);
      }
    } catch (err) {
      status.textContent = 'Connection error';
    }

    btn.classList.remove('recording');
    btn.innerHTML = '&#x1F3A4;';
    isRecording = false;
  }

  // ------- Text search -------
  const searchInput = document.getElementById('search-input');
  const clearBtn = document.getElementById('clear-btn');

  searchInput.addEventListener('input', function() {
    const val = this.value.trim();
    clearBtn.classList.toggle('visible', val.length > 0);

    clearTimeout(searchTimeout);
    if (val.length >= 2) {
      searchTimeout = setTimeout(() => textSearch(val), 150);
    } else {
      document.getElementById('results-list').innerHTML = '';
      document.getElementById('no-results').style.display = 'block';
    }
  });

  function clearSearch() {
    searchInput.value = '';
    clearBtn.classList.remove('visible');
    document.getElementById('results-list').innerHTML = '';
    document.getElementById('no-results').style.display = 'block';
  }

  async function textSearch(query) {
    let url;
    if (currentMode === 'first') {
      url = '/api/search?q=' + encodeURIComponent(query) + '&field=first';
    } else if (currentMode === 'last') {
      url = '/api/search?q=' + encodeURIComponent(query) + '&field=last';
    } else {
      url = '/api/search?q=' + encodeURIComponent(query);
    }

    try {
      const resp = await fetch(url);
      const data = await resp.json();
      renderResults(data.results);
    } catch (err) {
      console.error(err);
    }
  }

  // ------- Render results -------
  function renderResults(results) {
    const list = document.getElementById('results-list');
    const noResults = document.getElementById('no-results');

    if (!results || results.length === 0) {
      list.innerHTML = '';
      noResults.style.display = 'block';
      noResults.textContent = 'No matches found. Try again.';
      return;
    }

    noResults.style.display = 'none';
    list.innerHTML = results.map((r, i) => {
      const scoreClass = r.score >= 70 ? 'high' : r.score >= 45 ? 'mid' : '';
      return `
        <div class="result-item" onclick="selectStudent('${r.name.replace(/'/g, "\\'")}')">
          <span class="result-name">${r.name}</span>
          <span class="result-score ${scoreClass}">${Math.round(r.score)}%</span>
        </div>
      `;
    }).join('');
  }

  // ------- Student selection -------
  function selectStudent(name) {
    document.getElementById('selected-name').textContent = name;
    document.getElementById('selected-overlay').classList.add('visible');

    // Notify backend
    fetch('/api/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name })
    });
  }

  function dismissSelection() {
    document.getElementById('selected-overlay').classList.remove('visible');
  }
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/search")
def api_search():
    """Text search endpoint."""
    query = request.args.get("q", "").strip()
    field = request.args.get("field", "").strip()

    if not query:
        return jsonify({"results": []})

    if field in ("first", "last"):
        results = matcher.search_by_field(query, field=field, top_n=8)
    else:
        results = matcher.search(query, top_n=8, mode="text")

    return jsonify({"results": results})


@app.route("/api/voice", methods=["POST"])
def api_voice():
    """Voice search endpoint: record, recognize, match by LAST NAME only."""
    data = request.get_json() or {}
    duration = min(int(data.get("duration", 3)), 10)

    # Record audio
    wav_path = record_audio(duration=duration)
    if not wav_path:
        return jsonify({"error": "Could not record audio", "results": []})

    # Run PocketSphinx (grammar now only contains last names)
    heard = recognize_speech(wav_path)

    if not heard:
        return jsonify({"heard": "", "results": [], "error": "No speech detected"})

    # Search by last name using hybrid matching
    # This shows all students whose last name matches phonetically
    results = matcher.search_by_field(heard, field="last", top_n=10)

    return jsonify({"heard": heard, "results": results})


@app.route("/api/select", methods=["POST"])
def api_select():
    """Log selected student (hook for your carline system)."""
    data = request.get_json() or {}
    name = data.get("name", "")
    print(f"[SELECTED] {name}")
    # TODO: integrate with your carline/QR system here
    return jsonify({"ok": True, "name": name})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    global matcher, GRAMMAR_PATH, DICT_PATH

    parser = argparse.ArgumentParser(description="Carline Student Lookup")
    parser.add_argument("--students", required=True, help="Path to student CSV file")
    parser.add_argument("--grammar", default=None, help="Path to names.gram (optional)")
    parser.add_argument("--dict", default=None, help="Path to names.dict (optional)")
    parser.add_argument("--port", type=int, default=5000, help="Port (default 5000)")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default 0.0.0.0)")
    args = parser.parse_args()

    # Set PocketSphinx grammar/dict paths
    GRAMMAR_PATH = args.grammar
    DICT_PATH = args.dict

    # Load student matcher
    matcher = StudentMatcher(args.students)

    print(f"\nStarting on http://{args.host}:{args.port}")
    print(f"  Students: {args.students}")
    print(f"  Grammar:  {GRAMMAR_PATH or 'default'}")
    print(f"  Dict:     {DICT_PATH or 'default'}")
    print()

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()

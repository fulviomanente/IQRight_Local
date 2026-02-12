#!/usr/bin/env python3
"""
Packet Trace Diagnostic Tool

Traces failed packets through scanner → repeater → server → repeater → scanner
to identify where messages are getting lost.

Usage:
    python utility_tools/trace_packets.py /path/to/logs/
    python utility_tools/trace_packets.py /path/to/logs/ --date 2026-02-10
    python utility_tools/trace_packets.py /path/to/logs/ --all  (show successful too)

Expects log files in the folder (including rotated files):
    - IQRight_Scanner.debug, IQRight_Scanner.debug.1, ...
    - repeater_*.log, repeater_*.log.1, ...
    - IQRight_Server.debug, IQRight_Server.debug.1, ...
"""

import re
import sys
import os
import glob
from datetime import datetime, date
from collections import defaultdict

# --- Log line patterns ---

# Scanner patterns
# [TX] Sending (1): 102|ABC123|1 | seq=15
SCANNER_TX = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'\[TX\] Sending \((\d+)\): (.+?) \| seq=(\d+)'
)
# [TX] Send OK (1): ABC123 | seq=15
SCANNER_TX_OK = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'\[TX\] Send OK \((\d+)\): (.+?) \| seq=(\d+)'
)
# [TX] LoRa send failed (1): ABC123 | seq=15
SCANNER_TX_FAIL = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'\[TX\] LoRa send failed \((\d+)\): (.+?) \| seq=(\d+)'
)
# [RX] TIMEOUT waiting for response from Server
SCANNER_RX_TIMEOUT = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'\[RX\] TIMEOUT'
)
# [TX] FAILED after N attempts: payload | timeout=Xs
SCANNER_FINAL_FAIL = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'\[TX\] FAILED after (\d+) attempts: (.+?) \| timeout=(\d+)s'
)
# [RX] Response from Server: LoRaPacket(...)
SCANNER_RX_OK = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'\[RX\] Response from Server: LoRaPacket\(.*?seq=(\d+)'
)
# [RX] Payload: content
SCANNER_RX_PAYLOAD = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'\[RX\] Payload: (.+)'
)
# [CMD-RETRY] First attempt failed
SCANNER_CMD_RETRY = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'\[CMD-RETRY\] First attempt failed for (.+?),'
)

# Repeater patterns
# Forwarding packet: LoRaPacket(type=DATA, src=102, dst=1, seq=15, ttl=3)
REPEATER_FWD = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'Forwarding packet: LoRaPacket\(type=(\w+), src=(\d+), dst=(\d+), seq=(\d+), ttl=(\d+)'
)
# Dropped duplicate/TTL/etc
REPEATER_DROP = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'Dropped (\w+) packet.*?src=(\d+).*?seq=(\d+)'
)
# Failed to forward
REPEATER_FWD_FAIL = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'Failed to forward packet.*?src=(\d+).*?seq=(\d+)'
)

# Server patterns
# Received data from scanner N: Beacon=X, Code=Y, Distance=Z
SERVER_RX_DATA = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'Received data from scanner (\d+): Beacon=(\w+), Code=(\w+), Distance=(\d+)'
)
# Received command 'X' from scanner N
SERVER_RX_CMD = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r"Received command '(\w+)' from scanner (\d+)"
)
# Sent DATA to scanner N: payload [idx/total]
SERVER_TX = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'Sent (\w+) to scanner (\d+): (.+?) \[(\d+)/(\d+)\]'
)
# FAILED to send data/command to Scanner
SERVER_TX_FAIL = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'FAILED to send (\w+) to Scanner'
)
# Command ACK sent to scanner N
SERVER_CMD_ACK = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'Command ACK sent to scanner (\d+): (.+)'
)
# NOT_FOUND response sent
SERVER_NOT_FOUND = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'NOT_FOUND response sent to scanner (\d+) for code (\w+)'
)
# RESTRICTED response sent
SERVER_RESTRICTED = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'RESTRICTED response sent to scanner (\d+) for code (\w+)'
)
# [GRADE-FILTER] Filtered out
SERVER_GRADE_FILTER = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'\[GRADE-FILTER\] (.+)'
)
# No data found for code
SERVER_NO_DATA = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'No data found for code (\w+) from scanner (\d+)'
)
# [DEDUP]
SERVER_DEDUP = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*'
    r'\[DEDUP\] (.+)'
)


def parse_timestamp(ts_str: str) -> datetime:
    """Parse log timestamp to datetime."""
    try:
        return datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S,%f')
    except ValueError:
        return datetime.strptime(ts_str.split(',')[0], '%Y-%m-%d %H:%M:%S')


def load_log_files(log_dir: str, pattern: str) -> list:
    """Load and sort all matching log files (including rotated), return lines."""
    files = glob.glob(os.path.join(log_dir, pattern))
    # Also grab rotated files (.1, .2, etc.)
    files += glob.glob(os.path.join(log_dir, pattern + '.*'))
    # Filter out non-log extensions
    files = [f for f in files if not f.endswith('.gz')]

    all_lines = []
    for filepath in sorted(files):
        try:
            with open(filepath, 'r', errors='replace') as f:
                all_lines.extend(f.readlines())
        except Exception as e:
            print(f"  Warning: Could not read {filepath}: {e}")
    return all_lines


def filter_by_date(lines: list, target_date: str) -> list:
    """Filter log lines to only include those from target_date (YYYY-MM-DD)."""
    return [line for line in lines if line.startswith(target_date)]


def find_scanner_failures(scanner_lines: list) -> list:
    """
    Find all failed transmissions in scanner logs.
    Returns list of dicts with failure details.
    """
    failures = []
    # Track the current send context
    current_send = None

    for line in scanner_lines:
        # Track each TX attempt
        m = SCANNER_TX.search(line)
        if m:
            current_send = {
                'timestamp': m.group(1),
                'attempt': int(m.group(2)),
                'payload': m.group(3),
                'seq': m.group(4),
                'send_ok': False,
                'rx_timeout': False,
                'final_fail': False,
                'events': [f"  {m.group(1)} [SCANNER] TX attempt {m.group(2)}: {m.group(3)} (seq={m.group(4)})"]
            }
            continue

        # TX succeeded at LoRa level
        m = SCANNER_TX_OK.search(line)
        if m and current_send:
            current_send['send_ok'] = True
            current_send['events'].append(
                f"  {m.group(1)} [SCANNER] TX OK (LoRa send succeeded)"
            )
            continue

        # TX failed at LoRa level
        m = SCANNER_TX_FAIL.search(line)
        if m and current_send:
            current_send['events'].append(
                f"  {m.group(1)} [SCANNER] TX FAILED (LoRa send failed)"
            )
            continue

        # RX got response
        m = SCANNER_RX_OK.search(line)
        if m and current_send:
            current_send['events'].append(
                f"  {m.group(1)} [SCANNER] RX response received (seq={m.group(2)})"
            )
            current_send = None  # Success — reset context
            continue

        # RX timeout
        m = SCANNER_RX_TIMEOUT.search(line)
        if m and current_send:
            current_send['rx_timeout'] = True
            current_send['events'].append(
                f"  {m.group(1)} [SCANNER] RX TIMEOUT - no response from server"
            )
            continue

        # Final failure (all retries exhausted)
        m = SCANNER_FINAL_FAIL.search(line)
        if m:
            if current_send:
                current_send['final_fail'] = True
                current_send['events'].append(
                    f"  {m.group(1)} [SCANNER] FAILED after {m.group(2)} attempts: {m.group(3)}"
                )
                failures.append(current_send)
            else:
                failures.append({
                    'timestamp': m.group(1),
                    'attempt': int(m.group(2)),
                    'payload': m.group(3),
                    'seq': '?',
                    'events': [f"  {m.group(1)} [SCANNER] FAILED after {m.group(2)} attempts: {m.group(3)}"]
                })
            current_send = None
            continue

        # CMD retry (indicates first attempt failed)
        m = SCANNER_CMD_RETRY.search(line)
        if m:
            if current_send:
                current_send['events'].append(
                    f"  {m.group(1)} [SCANNER] CMD retry triggered for: {m.group(2)}"
                )

    # If there's an unresolved send with timeout, it's a failure
    if current_send and current_send.get('rx_timeout'):
        failures.append(current_send)

    return failures


def trace_in_repeater(repeater_lines: list, failure: dict, time_window_sec: int = 30) -> list:
    """Search repeater logs for activity related to this failure."""
    events = []
    fail_time = parse_timestamp(failure['timestamp'])
    seq = failure.get('seq', '?')

    for line in repeater_lines:
        # Check forwarding
        m = REPEATER_FWD.search(line)
        if m:
            line_time = parse_timestamp(m.group(1))
            time_diff = abs((line_time - fail_time).total_seconds())
            if time_diff <= time_window_sec:
                pkt_seq = m.group(5)
                pkt_src = m.group(3)
                pkt_dst = m.group(4)
                pkt_type = m.group(2)
                events.append(
                    f"  {m.group(1)} [REPEATER] Forwarded {pkt_type}: src={pkt_src} dst={pkt_dst} seq={pkt_seq} ttl={m.group(6)}"
                )
            continue

        # Check drops
        m = REPEATER_DROP.search(line)
        if m:
            line_time = parse_timestamp(m.group(1))
            time_diff = abs((line_time - fail_time).total_seconds())
            if time_diff <= time_window_sec:
                events.append(
                    f"  {m.group(1)} [REPEATER] DROPPED ({m.group(2)}): src={m.group(3)} seq={m.group(4)}"
                )
            continue

        # Check forward failures
        m = REPEATER_FWD_FAIL.search(line)
        if m:
            line_time = parse_timestamp(m.group(1))
            time_diff = abs((line_time - fail_time).total_seconds())
            if time_diff <= time_window_sec:
                events.append(
                    f"  {m.group(1)} [REPEATER] FORWARD FAILED: src={m.group(2)} seq={m.group(3)}"
                )

    return events


def trace_in_server(server_lines: list, failure: dict, time_window_sec: int = 30) -> list:
    """Search server logs for activity related to this failure."""
    events = []
    fail_time = parse_timestamp(failure['timestamp'])

    # Extract the QR code from the payload (format: "scanner_id|code|distance" or "cmd:command")
    payload = failure.get('payload', '')
    parts = payload.split('|')
    qr_code = parts[0] if len(parts) == 1 else (parts[1] if len(parts) >= 2 else payload)
    # For cmd payloads
    is_cmd = payload.startswith('cmd:')

    for line in server_lines:
        try:
            # Check for data reception matching this code
            m = SERVER_RX_DATA.search(line)
            if m:
                line_time = parse_timestamp(m.group(1))
                time_diff = abs((line_time - fail_time).total_seconds())
                if time_diff <= time_window_sec:
                    code = m.group(4)
                    scanner = m.group(2)
                    events.append(
                        f"  {m.group(1)} [SERVER] Received data: scanner={scanner} code={code}"
                    )
                continue

            # Check for command reception
            m = SERVER_RX_CMD.search(line)
            if m and is_cmd:
                line_time = parse_timestamp(m.group(1))
                time_diff = abs((line_time - fail_time).total_seconds())
                if time_diff <= time_window_sec:
                    events.append(
                        f"  {m.group(1)} [SERVER] Received command: '{m.group(1)}' from scanner {m.group(2)}"
                    )
                continue

            # Check for data/command sent back
            m = SERVER_TX.search(line)
            if m:
                line_time = parse_timestamp(m.group(1))
                time_diff = abs((line_time - fail_time).total_seconds())
                if time_diff <= time_window_sec:
                    events.append(
                        f"  {m.group(1)} [SERVER] Sent {m.group(2)} to scanner {m.group(3)}: {m.group(4)} [{m.group(5)}/{m.group(6)}]"
                    )
                continue

            # Check for send failures
            m = SERVER_TX_FAIL.search(line)
            if m:
                line_time = parse_timestamp(m.group(1))
                time_diff = abs((line_time - fail_time).total_seconds())
                if time_diff <= time_window_sec:
                    events.append(
                        f"  {m.group(1)} [SERVER] SEND FAILED: {m.group(2)}"
                    )
                continue

            # Command ACK
            m = SERVER_CMD_ACK.search(line)
            if m:
                line_time = parse_timestamp(m.group(1))
                time_diff = abs((line_time - fail_time).total_seconds())
                if time_diff <= time_window_sec:
                    events.append(
                        f"  {m.group(1)} [SERVER] Command ACK sent to scanner {m.group(2)}: {m.group(3)}"
                    )
                continue

            # NOT_FOUND
            m = SERVER_NOT_FOUND.search(line)
            if m:
                line_time = parse_timestamp(m.group(1))
                time_diff = abs((line_time - fail_time).total_seconds())
                if time_diff <= time_window_sec:
                    events.append(
                        f"  {m.group(1)} [SERVER] NOT_FOUND sent to scanner {m.group(2)} for code {m.group(3)}"
                    )
                continue

            # RESTRICTED
            m = SERVER_RESTRICTED.search(line)
            if m:
                line_time = parse_timestamp(m.group(1))
                time_diff = abs((line_time - fail_time).total_seconds())
                if time_diff <= time_window_sec:
                    events.append(
                        f"  {m.group(1)} [SERVER] RESTRICTED sent to scanner {m.group(2)} for code {m.group(3)}"
                    )
                continue

            # No data found
            m = SERVER_NO_DATA.search(line)
            if m:
                line_time = parse_timestamp(m.group(1))
                time_diff = abs((line_time - fail_time).total_seconds())
                if time_diff <= time_window_sec:
                    events.append(
                        f"  {m.group(1)} [SERVER] No data found for code {m.group(2)} from scanner {m.group(3)}"
                    )
                continue

            # Grade filter
            m = SERVER_GRADE_FILTER.search(line)
            if m:
                line_time = parse_timestamp(m.group(1))
                time_diff = abs((line_time - fail_time).total_seconds())
                if time_diff <= time_window_sec:
                    events.append(
                        f"  {m.group(1)} [SERVER] {m.group(2)}"
                    )
                continue

            # Dedup
            m = SERVER_DEDUP.search(line)
            if m:
                line_time = parse_timestamp(m.group(1))
                time_diff = abs((line_time - fail_time).total_seconds())
                if time_diff <= time_window_sec:
                    events.append(
                        f"  {m.group(1)} [SERVER] {m.group(2)}"
                    )

        except (ValueError, IndexError):
            continue

    return events


def diagnose_failure(scanner_events, repeater_events, server_events) -> str:
    """Analyze events to determine where the packet was lost."""
    has_repeater_fwd_to_server = any('[REPEATER] Forwarded' in e and 'dst=1' in e for e in repeater_events)
    has_server_rx = any('[SERVER] Received' in e for e in server_events)
    has_server_tx = any('[SERVER] Sent' in e or '[SERVER] Command ACK' in e for e in server_events)
    has_server_fail = any('[SERVER] SEND FAILED' in e for e in server_events)
    has_repeater_fwd_to_scanner = any('[REPEATER] Forwarded' in e and 'dst=1' not in e for e in repeater_events)
    has_repeater_drop = any('[REPEATER] DROPPED' in e for e in repeater_events)
    has_scanner_tx_fail = any('[SCANNER] TX FAILED' in e for e in scanner_events)

    if has_scanner_tx_fail:
        return "LOST AT SCANNER: LoRa radio failed to transmit"

    if not has_repeater_fwd_to_server and not has_server_rx:
        return "LOST BETWEEN SCANNER AND REPEATER: Packet never reached repeater or server"

    if has_repeater_drop:
        return "DROPPED BY REPEATER: Packet was dropped (duplicate/TTL)"

    if has_repeater_fwd_to_server and not has_server_rx:
        return "LOST BETWEEN REPEATER AND SERVER: Repeater forwarded but server never received"

    if has_server_rx and not has_server_tx:
        if any('No data found' in e for e in server_events):
            return "SERVER: Code not found in database (no response sent - pre-NOT_FOUND fix)"
        if any('GRADE-FILTER' in e for e in server_events):
            return "SERVER: All students filtered by grade restriction"
        return "LOST AT SERVER: Server received but never sent response"

    if has_server_fail:
        return "LOST AT SERVER: Server failed to transmit response"

    if has_server_tx and not has_repeater_fwd_to_scanner:
        return "LOST BETWEEN SERVER AND REPEATER (return): Server sent but repeater didn't forward back"

    if has_repeater_fwd_to_scanner:
        return "LOST BETWEEN REPEATER AND SCANNER (return): Repeater forwarded response but scanner didn't receive"

    if not repeater_events and not server_events:
        return "NO TRACE FOUND: No matching activity in repeater or server logs (check time sync between devices)"

    return "INCONCLUSIVE: Partial trace found - see events above"


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Trace failed packets through scanner → repeater → server pipeline'
    )
    parser.add_argument('log_dir', help='Directory containing all log files')
    parser.add_argument('--date', '-d', help='Date to analyze (YYYY-MM-DD). Default: today',
                        default=date.today().strftime('%Y-%m-%d'))
    parser.add_argument('--all', '-a', action='store_true',
                        help='Show all transmissions (not just failures)')
    parser.add_argument('--window', '-w', type=int, default=30,
                        help='Time window in seconds for correlating events (default: 30)')

    args = parser.parse_args()
    log_dir = args.log_dir
    target_date = args.date
    time_window = args.window

    if not os.path.isdir(log_dir):
        print(f"Error: {log_dir} is not a directory")
        sys.exit(1)

    print(f"{'=' * 70}")
    print(f"  IQRight Packet Trace Diagnostic")
    print(f"  Date: {target_date}")
    print(f"  Log directory: {log_dir}")
    print(f"  Time window: {time_window}s")
    print(f"{'=' * 70}")

    # Load all log files
    print("\nLoading logs...")
    scanner_lines = load_log_files(log_dir, 'IQRight_Scanner*')
    repeater_lines = load_log_files(log_dir, 'repeater_*')
    server_lines = load_log_files(log_dir, 'IQRight_Server*')

    print(f"  Scanner: {len(scanner_lines)} lines")
    print(f"  Repeater: {len(repeater_lines)} lines")
    print(f"  Server: {len(server_lines)} lines")

    if not scanner_lines:
        print("\nError: No scanner log files found. Expected IQRight_Scanner.debug")
        sys.exit(1)

    # Filter by date
    scanner_lines = filter_by_date(scanner_lines, target_date)
    repeater_lines = filter_by_date(repeater_lines, target_date)
    server_lines = filter_by_date(server_lines, target_date)

    print(f"\nFiltered to {target_date}:")
    print(f"  Scanner: {len(scanner_lines)} lines")
    print(f"  Repeater: {len(repeater_lines)} lines")
    print(f"  Server: {len(server_lines)} lines")

    # Find failures
    failures = find_scanner_failures(scanner_lines)

    if not failures:
        print(f"\nNo failed transmissions found for {target_date}.")
        print("All packets were acknowledged successfully.")
        sys.exit(0)

    print(f"\n{'=' * 70}")
    print(f"  FAILED TRANSMISSIONS: {len(failures)} found")
    print(f"{'=' * 70}")

    # Trace each failure
    for i, failure in enumerate(failures, 1):
        print(f"\n{'─' * 70}")
        print(f"  FAILURE #{i} | {failure['timestamp']} | payload: {failure.get('payload', '?')}")
        print(f"{'─' * 70}")

        # Scanner events
        print("\n  --- Scanner ---")
        for event in failure.get('events', []):
            print(event)

        # Trace in repeater
        repeater_events = trace_in_repeater(repeater_lines, failure, time_window)
        print("\n  --- Repeater ---")
        if repeater_events:
            for event in sorted(repeater_events):
                print(event)
        else:
            print("  (no matching activity found)")

        # Trace in server
        server_events = trace_in_server(server_lines, failure, time_window)
        print("\n  --- Server ---")
        if server_events:
            for event in sorted(server_events):
                print(event)
        else:
            print("  (no matching activity found)")

        # Diagnosis
        diagnosis = diagnose_failure(
            failure.get('events', []),
            repeater_events,
            server_events
        )
        print(f"\n  >>> DIAGNOSIS: {diagnosis}")

    # Summary
    print(f"\n{'=' * 70}")
    print(f"  SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total failures: {len(failures)}")

    # Count diagnosis categories
    categories = defaultdict(int)
    for failure in failures:
        repeater_events = trace_in_repeater(repeater_lines, failure, time_window)
        server_events = trace_in_server(server_lines, failure, time_window)
        diagnosis = diagnose_failure(failure.get('events', []), repeater_events, server_events)
        category = diagnosis.split(':')[0]
        categories[category] += 1

    print(f"\n  Breakdown:")
    for category, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"    {count}x {category}")

    print()


if __name__ == '__main__':
    main()

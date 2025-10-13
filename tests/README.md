# LoRa Packet Protocol Tests

Automated unit tests for the enhanced LoRa packet protocol.

## Test Categories

### 1. Local Tests (No Hardware Required)

These tests run entirely in software without requiring LoRa radio hardware. Perfect for development and CI/CD.

**Test Files:**
- `test_packet_serialization.py` - Binary packet serialization/deserialization
- `test_crc_validation.py` - CRC16 checksum validation
- `test_multi_packet.py` - Multi-packet sequence protocol
- `test_duplicate_detection.py` - Duplicate packet detection and filtering
- `test_repeater_logic.py` - Repeater forwarding and TTL management

### 2. Hardware Tests (Requires LoRa Radio)

These tests require actual LoRa hardware (RFM95x/SX1262) to run. See `../LORA_TESTING.md` for details.

## Quick Start

### Run All Local Tests

```bash
cd tests
chmod +x *.sh
./run_all_local_tests.sh
```

This runs all 5 test suites and provides a summary.

### Run Single Test

```bash
./run_single_test.sh test_packet_serialization.py
```

### Generate Test Data

```bash
./generate_test_data.sh
```

This creates `test_data.json` with dummy student records, QR codes, and commands for testing.

## Test Coverage

### Packet Serialization Tests
- ✅ Basic roundtrip (serialize → deserialize)
- ✅ Large payloads (231 bytes max)
- ✅ Payload truncation for oversized data
- ✅ All packet types (DATA, ACK, CMD, BEACON)

### CRC Validation Tests
- ✅ Corrupted payload detection
- ✅ Corrupted header detection
- ✅ Valid packets pass CRC
- ✅ Multiple corruption patterns
- ✅ Boundary conditions (empty, single byte)

### Multi-Packet Tests
- ✅ FIRST/MORE/LAST flags
- ✅ Single packet (ONLY flag)
- ✅ Sequence serialization/deserialization
- ✅ LoRaTransceiver helper methods
- ✅ Multi-packet index/total tracking

### Duplicate Detection Tests
- ✅ Duplicate rejection
- ✅ Sequence number wrap (65535 → 0)
- ✅ Loop detection (own packets)
- ✅ TTL expiration
- ✅ Address filtering (not for me)
- ✅ Repeater forwarding logic
- ✅ Broadcast packets (dest=0)
- ✅ seen_packets cleanup

### Repeater Logic Tests
- ✅ Packet forwarding with updated sender
- ✅ TTL decrement through chain
- ✅ Payload preservation
- ✅ Serialization of repeated packets
- ✅ Multi-hop path tracking
- ✅ Timestamp preservation
- ✅ Multi-packet info preservation

## Expected Results

All local tests should pass without errors:

```
========================================================================
TEST SUMMARY
========================================================================
Total Tests:  5
Passed:       5
Failed:       0
========================================================================

✅ ALL TESTS PASSED
```

## Test Data Structure

The `test_data_generator.py` creates JSON with:

```json
{
  "students": [
    {
      "name": "Emma Smith",
      "hierarchyLevel1": "First Grade",
      "hierarchyLevel2": "Mrs. Anderson",
      "hierarchyID": "01",
      "externalNumber": "123456789",
      "externalID": "123456789",
      "distance": 1,
      "node": 102,
      "location": "Main Entrance"
    }
  ],
  "qr_codes": ["123456789", ...],
  "scan_requests": ["102|123456789|1", ...],
  "commands": ["cmd:break", "cmd:release", ...]
}
```

## Troubleshooting

### ImportError: No module named 'lora'

Make sure you're running from the tests directory or that the parent directory is in PYTHONPATH:

```bash
cd tests
python3 test_packet_serialization.py
```

### Hardware initialization errors in LOCAL mode

Tests automatically set `LOCAL=TRUE` environment variable to bypass hardware initialization. If you see hardware errors, check that `os.getenv("LOCAL")` is properly checked in your code.

### Permission denied on shell scripts

Make scripts executable:

```bash
chmod +x *.sh
```

## Next Steps

1. ✅ Run all local tests to validate packet protocol
2. ⏳ Generate test data for integration testing
3. ⏳ Deploy to hardware for integration tests (see `../LORA_TESTING.md`)
4. ⏳ Run end-to-end tests with server + scanner + repeater

## Contributing

When adding new tests:

1. Create test file: `test_<feature>.py`
2. Follow existing test structure
3. Add test to `run_all_local_tests.sh`
4. Update this README with test description
5. Ensure tests can run without hardware (use `LOCAL=TRUE`)

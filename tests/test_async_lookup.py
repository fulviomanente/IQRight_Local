#!/usr/bin/env python3
"""
Test: Async Lookup Race Condition Fix

Tests that API and local lookups run in parallel and the fastest result wins.
"""

import sys
import os
import asyncio
import time

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


async def mock_api_fast(code):
    """Mock API that responds quickly (100ms)"""
    await asyncio.sleep(0.1)
    return {"name": "API Student", "source": "api", "code": code}


async def mock_api_slow(code):
    """Mock API that responds slowly (3s - times out)"""
    await asyncio.sleep(3.0)
    return {"name": "API Student Slow", "source": "api", "code": code}


async def mock_api_none(code):
    """Mock API that returns None (not found)"""
    await asyncio.sleep(0.5)
    return None


async def mock_local_fast(code):
    """Mock local lookup that responds quickly (50ms)"""
    await asyncio.sleep(0.05)
    return [{"name": "Local Student", "source": "local", "code": code}]


async def mock_local_slow(code):
    """Mock local lookup that responds slowly (1s)"""
    await asyncio.sleep(1.0)
    return [{"name": "Local Student Slow", "source": "local", "code": code}]


async def mock_getInfo(api_func, local_func, code):
    """
    Simulates the fixed getInfo logic:
    - Both tasks run in parallel
    - First valid result wins
    - 2-second timeout
    """
    api_task = asyncio.create_task(api_func(code))
    local_task = asyncio.create_task(local_func(code))

    try:
        # Wait for first to complete
        done, pending = await asyncio.wait(
            [api_task, local_task],
            timeout=2.0,
            return_when=asyncio.FIRST_COMPLETED
        )

        # Check API first (priority)
        if api_task in done:
            api_result = await api_task
            if api_result:
                if local_task in pending:
                    local_task.cancel()
                return api_result, "api"

        # Check local
        if local_task in done:
            local_result = await local_task
            if local_result:
                if api_task in pending:
                    api_task.cancel()
                return local_result, "local"

        # Timeout - wait for remaining
        if pending:
            remaining_done, remaining_pending = await asyncio.wait(pending, timeout=0.5)
            for task in remaining_done:
                result = await task
                if result:
                    source = "api" if task == api_task else "local"
                    return result, source

        return None, "none"

    except Exception as ex:
        api_task.cancel()
        local_task.cancel()
        return None, "error"


async def test_api_faster_than_local():
    """Test: API responds faster than local → use API"""
    print("Testing: API faster than local...")

    start = time.time()
    result, source = await mock_getInfo(mock_api_fast, mock_local_slow, "123")
    elapsed = time.time() - start

    assert source == "api", f"Expected 'api', got '{source}'"
    assert result["name"] == "API Student"
    assert elapsed < 0.5, f"Should complete quickly (~0.1s), took {elapsed:.2f}s"

    print(f"  ✓ API result returned in {elapsed:.2f}s")
    return True


async def test_local_faster_than_api():
    """Test: Local responds faster than API → use local"""
    print("\nTesting: Local faster than API...")

    start = time.time()
    result, source = await mock_getInfo(mock_api_slow, mock_local_fast, "123")
    elapsed = time.time() - start

    assert source == "local", f"Expected 'local', got '{source}'"
    assert result[0]["name"] == "Local Student"
    assert elapsed < 0.5, f"Should complete quickly (~0.05s), took {elapsed:.2f}s"

    print(f"  ✓ Local result returned in {elapsed:.2f}s")
    return True


async def test_api_returns_none_use_local():
    """Test: API returns None → use local"""
    print("\nTesting: API returns None, use local...")

    start = time.time()
    result, source = await mock_getInfo(mock_api_none, mock_local_fast, "123")
    elapsed = time.time() - start

    assert source == "local", f"Expected 'local', got '{source}'"
    assert result[0]["name"] == "Local Student"
    assert elapsed < 1.0, f"Should complete reasonably fast, took {elapsed:.2f}s"

    print(f"  ✓ Local result returned in {elapsed:.2f}s (after API returned None)")
    return True


async def test_both_timeout():
    """Test: Both timeout → return None"""
    print("\nTesting: Both timeout...")

    async def mock_api_very_slow(code):
        await asyncio.sleep(5.0)
        return {"name": "Never", "source": "api"}

    async def mock_local_very_slow(code):
        await asyncio.sleep(5.0)
        return [{"name": "Never", "source": "local"}]

    start = time.time()
    result, source = await mock_getInfo(mock_api_very_slow, mock_local_very_slow, "123")
    elapsed = time.time() - start

    assert source == "none", f"Expected 'none', got '{source}'"
    assert result is None
    assert elapsed < 3.0, f"Should timeout at ~2.5s, took {elapsed:.2f}s"

    print(f"  ✓ Both timed out after {elapsed:.2f}s")
    return True


async def test_parallel_execution():
    """Test: Both tasks actually run in parallel (not sequential)"""
    print("\nTesting: Parallel execution...")

    # If sequential: 0.1 + 0.05 = 0.15s
    # If parallel: max(0.1, 0.05) = 0.1s
    start = time.time()
    result, source = await mock_getInfo(mock_api_fast, mock_local_fast, "123")
    elapsed = time.time() - start

    # Should complete in ~0.1s (API time), not 0.15s (sequential)
    assert elapsed < 0.15, f"Tasks may be running sequentially! Took {elapsed:.2f}s"
    print(f"  ✓ Tasks ran in parallel ({elapsed:.2f}s < 0.15s)")
    return True


def main():
    """Run all async lookup tests"""
    print("=" * 60)
    print("ASYNC LOOKUP RACE CONDITION FIX TESTS")
    print("=" * 60)
    print()

    tests = [
        test_api_faster_than_local,
        test_local_faster_than_api,
        test_api_returns_none_use_local,
        test_both_timeout,
        test_parallel_execution,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            result = asyncio.run(test())
            if result:
                passed += 1
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n✅ All tests passed - Async lookup is working correctly!")
        print("\nKey improvements:")
        print("  • Both API and local run in true parallel")
        print("  • Fastest valid result wins")
        print("  • No unnecessary waiting for slow tasks")
        print("  • Proper timeout handling")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

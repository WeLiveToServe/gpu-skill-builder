"""Shared pytest fixtures."""

import asyncio

import pytest


@pytest.fixture(scope="session", autouse=True)
def _session_event_loop():
    """
    Ensure legacy tests using asyncio.get_event_loop() continue to work on
    Python 3.12+, where no loop is created by default.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield
    finally:
        loop.close()
        asyncio.set_event_loop(None)

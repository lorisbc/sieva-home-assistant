"""Test the Sieva client outside Home Assistant.

Usage:
    python3 -m venv .venv && .venv/bin/pip install aiohttp
    SIEVA_LOGIN=... SIEVA_PASSWORD=... .venv/bin/python scripts/sieva_cli.py
    (RAW=1 to also print the raw portal answers)
"""

import asyncio
import importlib.util
import json
import logging
import os
import sys
from pathlib import Path

import aiohttp

_API_PATH = Path(__file__).parent.parent / "custom_components" / "sieva" / "api.py"
_spec = importlib.util.spec_from_file_location("sieva_api", _API_PATH)
api = importlib.util.module_from_spec(_spec)
sys.modules["sieva_api"] = api
_spec.loader.exec_module(api)


async def main() -> None:
    logging.basicConfig(level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO)
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
        client = api.SievaClient(
            session, os.environ["SIEVA_LOGIN"], os.environ["SIEVA_PASSWORD"]
        )
        points = await client.async_get_data()
        if not points:
            print("No installation point found")
        for point, data in points.items():
            print(
                f"=== {point} | installation point {data.installation_point} | meter {data.meter} | {data.address}"
            )
            if os.getenv("RAW"):
                print(json.dumps(data.raw, indent=2, ensure_ascii=False))
            for year, value in data.yearly.items():
                print(f"  {year}: {value} m³")
            print(f"  TOTAL: {data.total} m³ (data until {data.last_day})")
            print("  Last periods (end date: m³):")
            for end in sorted(data.consumption)[-5:]:
                print(f"    {end}: {data.consumption[end]}")


if __name__ == "__main__":
    asyncio.run(main())

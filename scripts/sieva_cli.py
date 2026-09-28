"""Test the Sieva client outside Home Assistant.

Usage:
    pip install aiohttp
    SIEVA_LOGIN=... SIEVA_PASSWORD=... python scripts/sieva_cli.py
    (SIEVA_PI=... to force the installation point)
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
    login, password = os.environ["SIEVA_LOGIN"], os.environ["SIEVA_PASSWORD"]
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
        points = await api.SievaClient(
            session, login, password
        ).async_get_delivery_points()
        print("--- Points d'installation ---")
        for point, address in points.items():
            print(f"  {point}: {address}")

        delivery_point = os.getenv("SIEVA_PI") or next(iter(points), None)
        if delivery_point is None:
            raise SystemExit("Aucun point trouvé, relancez avec SIEVA_PI=...")

        data = await api.SievaClient(
            session, login, password, delivery_point
        ).async_get_data()
        print(f"--- GetGraphRelevesData ({delivery_point}, brut) ---")
        print(json.dumps(data.raw, indent=2, ensure_ascii=False))
        print("--- Par année ---")
        for year, value in sorted(data.yearly.items()):
            print(f"  {year}: {value} m³")
        print(f"INDEX: {data.total} m³")


if __name__ == "__main__":
    asyncio.run(main())

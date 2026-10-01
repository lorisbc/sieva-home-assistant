"""Async client for the Sieva customer portal (ael.sieva.fr).

This module intentionally does not depend on Home Assistant so it can be
used from the standalone debug script in ``scripts/sieva_cli.py``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import json
import logging
import re
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://ael.sieva.fr/Portail/fr-FR"
LOGIN_URL = f"{BASE_URL}/Connexion/Login"
SUBSCRIPTION_URL = f"{BASE_URL}/Usager/Abonnement/Synthese/{{}}"
DELIVERY_POINTS_URL = f"{BASE_URL}/Usager/Abonnement/AjaxPointDInstallationSynchros"
GRAPH_URL = f"{BASE_URL}/Usager/Abonnement/GetGraphRelevesData"
READINGS_URL = f"{BASE_URL}/Usager/Abonnement/AjaxReleveSynchros"

PORTAL_TZ = ZoneInfo("Europe/Paris")
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=60)
XHR_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}
# Minimal jQuery DataTables query: all rows (iDisplayLength=-1).
DATATABLES_FORM = {"sEcho": "1", "iDisplayStart": "0", "iDisplayLength": "-1"}

_TOKEN_RE = re.compile(
    r'name="__RequestVerificationToken"[^>]*?value="([^"]+)"', re.IGNORECASE
)
_SUBSCRIPTION_RE = re.compile(r"/Usager/Abonnement/\w+/(\d+)", re.IGNORECASE)
_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


class SievaError(Exception):
    """Base error for the Sieva client."""


class SievaAuthError(SievaError):
    """Credentials were rejected or the session expired."""


class SievaConnectionError(SievaError):
    """The portal could not be reached."""


class SievaParseError(SievaError):
    """The portal answered with data we could not understand."""


@dataclass
class SievaData:
    """Consumption of one installation point."""

    # {end of period: m³ consumed during the period}, see parse_graph_payload
    consumption: dict[date, float]
    address: str = ""
    installation_point: str = ""  # number shown on the portal, e.g. 6900000123
    meter: str = ""  # physical meter serial number, e.g. C15FA012345
    raw: Any = field(default=None, repr=False)

    @property
    def total(self) -> float:
        """Cumulated consumption since the start of the history, in m³."""
        return round(sum(self.consumption.values()), 3)

    @property
    def yearly(self) -> dict[str, float]:
        """Consumption per calendar year, in m³."""
        result: dict[str, float] = {}
        for end, value in self.consumption.items():
            year = str((end - timedelta(days=1)).year)
            result[year] = result.get(year, 0.0) + value
        return {year: round(value, 3) for year, value in sorted(result.items())}

    @property
    def last_day(self) -> date | None:
        """Last day included in the data."""
        if not self.consumption:
            return None
        return max(self.consumption) - timedelta(days=1)


def parse_graph_payload(payload: Any) -> dict[date, float]:
    """Extract ``{end of period: m³}`` from a ``GetGraphRelevesData`` answer.

    The portal returns Chart.js data: ``{"labels": ["dd/mm/yyyy", ...],
    "datasets": [{"label": "<point>", "data": [...]}]}``. Each label is the
    END of its period: with the ``Annee`` granularity, ``01/01/2026`` is the
    consumption of 2025; with ``Mois``, ``01/10/2026`` is September; with
    ``Jour``, ``01/10/2026`` is September 30th. Datasets are summed.
    """
    try:
        labels = payload["labels"]
        datasets = payload["datasets"]
    except (TypeError, KeyError) as err:
        raise SievaParseError(
            f"Unexpected GetGraphRelevesData format: {payload!r:.200}"
        ) from err

    result: dict[date, float] = {}
    for dataset in datasets:
        for label, value in zip(labels, dataset.get("data") or [], strict=False):
            if value is None or (match := _DATE_RE.search(str(label))) is None:
                continue
            day, month, year = (int(part) for part in match.groups())
            end = date(year, month, day)
            result[end] = result.get(end, 0.0) + float(value)
    return result


def merge_periods(*series: dict[date, float]) -> dict[date, float]:
    """Merge series from the coarsest to the finest without overlap.

    The yearly series only covers finished years and the monthly one finished
    months: each finer series only adds the periods after the last date
    already covered.
    """
    merged: dict[date, float] = {}
    for values in series:
        last = max(merged, default=None)
        merged.update(
            {end: value for end, value in values.items() if last is None or end > last}
        )
    return merged


def parse_delivery_points(payload: Any) -> dict[str, dict[str, str]]:
    """Extract ``{pointDInstallationId: {address, installation_point}}``.

    DataTables rows: ``[number, address, number, address, contract, ..., id]``
    where ``id`` is the internal id used by the API and ``number`` the
    installation point number shown on the portal.
    """
    try:
        rows = payload["aaData"]
    except (TypeError, KeyError) as err:
        raise SievaParseError(
            "Unexpected AjaxPointDInstallationSynchros format"
        ) from err
    return {
        str(row[-1]): {
            "address": " ".join(str(row[1]).replace("(France)", "").split()),
            "installation_point": str(row[0]).strip(),
        }
        for row in rows
        if len(row) > 1 and str(row[-1]).isdigit()
    }


def parse_meter(payload: Any) -> str:
    """Return the serial number of the meter of the most recent reading.

    DataTables rows: ``[meter, "dd/mm/yyyy", mode, _, index, label, m³, ...]``.
    """
    try:
        rows = [row for row in payload["aaData"] if len(row) > 1 and row[0]]
    except (TypeError, KeyError) as err:
        raise SievaParseError("Unexpected AjaxReleveSynchros format") from err
    if not rows:
        return ""
    latest = max(rows, key=lambda row: str(row[1]).split("/")[::-1])
    return str(latest[0]).strip()


def parse_subscriptions(html: str) -> list[str]:
    """Extract the subscription ids linked from a portal page."""
    return list(dict.fromkeys(_SUBSCRIPTION_RE.findall(html)))


class SievaClient:
    """Minimal client for the Sieva portal (one account)."""

    def __init__(
        self, session: aiohttp.ClientSession, login: str, password: str
    ) -> None:
        self._session = session
        self._login = login
        self._password = password

    async def _request(self, method: str, url: str, **kwargs: Any) -> tuple[str, str]:
        """Perform a request, return ``(body, final_url)``."""
        try:
            async with self._session.request(
                method, url, timeout=REQUEST_TIMEOUT, **kwargs
            ) as resp:
                resp.raise_for_status()
                return await resp.text(), str(resp.url)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise SievaConnectionError(
                f"Cannot reach the Sieva portal ({url}): {err}"
            ) from err

    async def _request_json(self, method: str, url: str, **kwargs: Any) -> Any:
        """Perform an XHR request and decode the JSON answer."""
        headers = {**XHR_HEADERS, **kwargs.pop("headers", {})}
        body, final_url = await self._request(method, url, headers=headers, **kwargs)
        if "/Connexion/Login" in final_url:
            raise SievaAuthError("Sieva session expired")
        try:
            return json.loads(body)
        except ValueError as err:
            raise SievaParseError(
                f"Non-JSON answer from {url}: {body[:200]!r}"
            ) from err

    async def async_login(self) -> str:
        """Open a new authenticated session, return the landing page HTML."""
        self._session.cookie_jar.clear()
        page, _ = await self._request("GET", LOGIN_URL)
        if (match := _TOKEN_RE.search(page)) is None:
            raise SievaParseError("__RequestVerificationToken not found")

        body, final_url = await self._request(
            "POST",
            LOGIN_URL,
            data={
                "Login": self._login,
                "MotDePasse": self._password,
                "__RequestVerificationToken": match.group(1),
            },
        )
        # A failed login renders the login form again.
        if "/Connexion/Login" in final_url and 'id="MotDePasse"' in body:
            raise SievaAuthError("Sieva credentials rejected")
        return body

    async def _async_get_delivery_points(
        self, landing: str
    ) -> dict[str, dict[str, str]]:
        """List the installation points of every subscription.

        The portal keeps the "current subscription" in the session: open each
        subscription page, then list its installation points.
        """
        points: dict[str, dict[str, str]] = {}
        for subscription in parse_subscriptions(landing):
            subscription_url = SUBSCRIPTION_URL.format(subscription)
            await self._request("GET", subscription_url)
            payload = await self._request_json(
                "POST",
                DELIVERY_POINTS_URL,
                data=DATATABLES_FORM,
                headers={"Referer": subscription_url},
            )
            points.update(parse_delivery_points(payload))
        return points

    async def _async_get_graph(
        self, delivery_point: str, granularity: str, start: str = ""
    ) -> Any:
        """Return the raw consumption of an installation point."""
        return await self._request_json(
            "POST",
            GRAPH_URL,
            json={
                "pointDInstallationId": delivery_point,
                "dateDebut": start,
                "dateFin": "",
                "granularite": granularity,
            },
        )

    async def _async_get_meter(self, delivery_point: str) -> str:
        """Return the meter serial number (optional, empty if unavailable)."""
        try:
            payload = await self._request_json(
                "POST",
                READINGS_URL,
                params={"pointDInstallationId": delivery_point},
                data=DATATABLES_FORM,
            )
            return parse_meter(payload)
        except SievaParseError as err:
            _LOGGER.debug(
                "Meter serial number unavailable for %s: %s", delivery_point, err
            )
            return ""

    async def async_get_data(self) -> dict[str, SievaData]:
        """Log in once and fetch every installation point of the account."""
        landing = await self.async_login()
        points = await self._async_get_delivery_points(landing)
        _LOGGER.debug("Installation points found: %s", points)
        data: dict[str, SievaData] = {}
        # Finished years, finished months since January of last year (the
        # portal keeps 24 months), then days (it keeps about 6 months).
        granularities = {
            "Annee": "",
            "Mois": f"01/01/{datetime.now(PORTAL_TZ).year - 1}",
            "Jour": "",
        }
        for point, info in points.items():
            raw = {
                granularity: await self._async_get_graph(point, granularity, start)
                for granularity, start in granularities.items()
            }
            _LOGGER.debug("GetGraphRelevesData %s: %s", point, raw)
            data[point] = SievaData(
                consumption=merge_periods(
                    *(parse_graph_payload(payload) for payload in raw.values())
                ),
                meter=await self._async_get_meter(point),
                raw=raw,
                **info,
            )
        return data

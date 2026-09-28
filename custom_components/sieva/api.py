"""Async client for the Sieva customer portal (ael.sieva.fr).

This module intentionally does not depend on Home Assistant so it can be
used from the standalone debug script in ``scripts/sieva_cli.py``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://ael.sieva.fr/Portail/fr-FR"
LOGIN_URL = f"{BASE_URL}/Connexion/Login"
GRAPH_URL = f"{BASE_URL}/Usager/Abonnement/GetGraphRelevesData"

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=60)

_TOKEN_RE = re.compile(
    r'name="__RequestVerificationToken"[^>]*?value="([^"]+)"', re.IGNORECASE
)
_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")

# Keys (lower-cased) that are likely to hold the consumption value / label.
_VALUE_HINTS = ("consommation", "conso", "volume", "quantite", "valeur", "value", "y")
_LABEL_HINTS = ("annee", "year", "periode", "date", "libelle", "label", "name", "x")


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
    """Consumption data returned by the portal."""

    yearly: dict[str, float]
    raw: Any = field(default=None, repr=False)

    @property
    def total(self) -> float:
        """Cumulated consumption since the start of the contract, in m³."""
        return round(sum(self.yearly.values()), 3)


def _to_float(value: Any) -> float | None:
    """Convert a portal value (number or French formatted string) to float."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
        cleaned = cleaned.removesuffix("m³").removesuffix("m3")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _normalize_label(label: Any, index: int) -> str:
    """Return the year contained in a label, or the label itself."""
    text = str(label) if label is not None else ""
    if match := _YEAR_RE.search(text):
        return match.group(1)
    return text or f"#{index}"


def _pick_key(keys: list[str], hints: tuple[str, ...]) -> str | None:
    lowered = {key.lower(): key for key in keys}
    for hint in hints:
        for low, key in lowered.items():
            if low == hint:
                return key
    for hint in hints:
        if len(hint) < 3:
            continue
        for low, key in lowered.items():
            if hint in low:
                return key
    return None


def _from_records(records: list[dict[str, Any]]) -> dict[str, float] | None:
    """Parse a list of objects such as ``[{"Annee": 2024, "Consommation": 42}]``."""
    keys = list(records[0].keys())
    numeric_keys = [
        key
        for key in keys
        if all(_to_float(rec.get(key)) is not None for rec in records)
    ]
    value_key = _pick_key(numeric_keys, _VALUE_HINTS)
    if value_key is None:
        return None
    label_key = _pick_key([k for k in keys if k != value_key], _LABEL_HINTS)
    result: dict[str, float] = {}
    for index, record in enumerate(records):
        label = _normalize_label(record.get(label_key) if label_key else None, index)
        result[label] = result.get(label, 0.0) + (_to_float(record[value_key]) or 0.0)
    return result


def _from_series(data: dict[str, Any]) -> dict[str, float] | None:
    """Parse a chart structure such as ``{"categories": [...], "series": [...]}``."""
    series_key = _pick_key(list(data.keys()), ("series", "datasets"))
    categories_key = _pick_key(list(data.keys()), ("categories", "labels", "xaxis"))
    if series_key is None or not isinstance(data[series_key], list):
        return None
    series = [s for s in data[series_key] if isinstance(s, dict)]
    if not series:
        return None
    chosen = next(
        (
            s
            for s in series
            if "conso" in str(s.get("name", s.get("label", ""))).lower()
        ),
        series[0],
    )
    points = chosen.get("data")
    if not isinstance(points, list):
        return None
    categories = data.get(categories_key) if categories_key else None
    if isinstance(categories, dict):
        categories = categories.get("categories")
    result: dict[str, float] = {}
    for index, point in enumerate(points):
        label: Any = None
        if isinstance(point, dict):
            value = _to_float(point.get("y", point.get("value")))
            label = point.get("name", point.get("x"))
        elif isinstance(point, list) and len(point) >= 2:
            label, value = point[0], _to_float(point[1])
        else:
            value = _to_float(point)
        if label is None and isinstance(categories, list) and index < len(categories):
            label = categories[index]
        if value is None:
            continue
        key = _normalize_label(label, index)
        result[key] = result.get(key, 0.0) + value
    return result or None


def parse_graph_payload(payload: Any) -> dict[str, float]:
    """Extract ``{year: m³}`` from the ``GetGraphRelevesData`` JSON answer."""
    # ASP.NET endpoints sometimes return a JSON-encoded string.
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError as err:
            raise SievaParseError("Réponse texte non JSON") from err

    if (
        isinstance(payload, list)
        and payload
        and all(isinstance(r, dict) for r in payload)
    ):
        if (result := _from_records(payload)) is not None:
            return result

    if isinstance(payload, dict):
        if (result := _from_series(payload)) is not None:
            return result
        # Look into common wrappers ("d", "Data", "Releves", ...).
        for value in payload.values():
            if isinstance(value, (dict, list, str)) and value:
                try:
                    return parse_graph_payload(value)
                except SievaParseError:
                    continue

    raise SievaParseError("Format de réponse GetGraphRelevesData non reconnu")


class SievaClient:
    """Minimal client for the Sieva portal."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        login: str,
        password: str,
        delivery_point: str,
    ) -> None:
        self._session = session
        self._login = login
        self._password = password
        self._delivery_point = str(delivery_point).strip()

    async def async_login(self) -> None:
        """Open a new authenticated session on the portal."""
        self._session.cookie_jar.clear()
        try:
            async with self._session.get(LOGIN_URL, timeout=REQUEST_TIMEOUT) as resp:
                resp.raise_for_status()
                page = await resp.text()
            match = _TOKEN_RE.search(page)
            if match is None:
                raise SievaParseError("Jeton __RequestVerificationToken introuvable")

            async with self._session.post(
                LOGIN_URL,
                data={
                    "Login": self._login,
                    "MotDePasse": self._password,
                    "__RequestVerificationToken": match.group(1),
                },
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                body = await resp.text()
                final_url = str(resp.url)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise SievaConnectionError(f"Portail Sieva injoignable: {err}") from err

        # A failed login renders the login form again.
        if "/Connexion/Login" in final_url and 'id="MotDePasse"' in body:
            raise SievaAuthError("Identifiants Sieva refusés")

    async def async_get_graph_payload(self) -> Any:
        """Return the raw yearly consumption JSON."""
        body = {
            "pointDInstallationId": self._delivery_point,
            "dateDebut": "",
            "dateFin": "",
            "granularite": "Annee",
        }
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
        try:
            async with self._session.post(
                GRAPH_URL, json=body, headers=headers, timeout=REQUEST_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
                final_url = str(resp.url)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise SievaConnectionError(f"Erreur GetGraphRelevesData: {err}") from err

        if "/Connexion/Login" in final_url:
            raise SievaAuthError("Session Sieva expirée")
        try:
            return json.loads(text)
        except ValueError as err:
            raise SievaParseError(
                f"Réponse non JSON de GetGraphRelevesData: {text[:200]!r}"
            ) from err

    async def async_get_data(self) -> SievaData:
        """Log in and fetch the yearly consumption."""
        await self.async_login()
        raw = await self.async_get_graph_payload()
        _LOGGER.debug("GetGraphRelevesData payload: %s", raw)
        return SievaData(yearly=parse_graph_payload(raw), raw=raw)

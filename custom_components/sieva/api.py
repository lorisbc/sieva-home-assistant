"""Async client for the Sieva customer portal (ael.sieva.fr).

This module intentionally does not depend on Home Assistant so it can be
used from the standalone debug script in ``scripts/sieva_cli.py``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import logging
import re
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://ael.sieva.fr/Portail/fr-FR"
LOGIN_URL = f"{BASE_URL}/Connexion/Login"
SYNTHESE_URL = f"{BASE_URL}/Usager/Abonnement/Synthese/{{}}"
DELIVERY_POINTS_URL = f"{BASE_URL}/Usager/Abonnement/AjaxPointDInstallationSynchros"
GRAPH_URL = f"{BASE_URL}/Usager/Abonnement/GetGraphRelevesData"
READINGS_URL = f"{BASE_URL}/Usager/Abonnement/AjaxReleveSynchros"

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
_ABONNEMENT_RE = re.compile(r"/Usager/Abonnement/\w+/(\d+)", re.IGNORECASE)
_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


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

    yearly: dict[str, float]
    address: str = ""
    installation_point: str = ""  # number shown on the portal, e.g. 6904900904
    meter: str = ""  # physical meter serial number, e.g. C15FA046458
    raw: Any = field(default=None, repr=False)

    @property
    def total(self) -> float:
        """Cumulated consumption since the start of the contract, in m³."""
        return round(sum(self.yearly.values()), 3)


def parse_graph_payload(payload: Any) -> dict[str, float]:
    """Extract ``{year: m³}`` from the ``GetGraphRelevesData`` answer.

    The portal returns Chart.js data: ``{"labels": [...], "datasets":
    [{"label": "<meter>", "data": [...]}]}``. Every dataset (one per meter)
    is summed so a meter replacement does not break the total.
    """
    try:
        labels = payload["labels"]
        datasets = payload["datasets"]
    except (TypeError, KeyError) as err:
        raise SievaParseError(
            f"Format GetGraphRelevesData inattendu: {payload!r:.200}"
        ) from err

    result: dict[str, float] = {}
    for dataset in datasets:
        for label, value in zip(labels, dataset.get("data") or [], strict=False):
            if value is None:
                continue
            match = _YEAR_RE.search(str(label))
            key = match.group(1) if match else str(label)
            result[key] = result.get(key, 0.0) + float(value)
    return result


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
            "Format AjaxPointDInstallationSynchros inattendu"
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
        raise SievaParseError("Format AjaxReleveSynchros inattendu") from err
    if not rows:
        return ""
    latest = max(rows, key=lambda row: str(row[1]).split("/")[::-1])
    return str(latest[0]).strip()


def parse_abonnements(html: str) -> list[str]:
    """Extract the subscription ids linked from a portal page."""
    return list(dict.fromkeys(_ABONNEMENT_RE.findall(html)))


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
                f"Portail Sieva injoignable ({url}): {err}"
            ) from err

    async def _request_json(self, method: str, url: str, **kwargs: Any) -> Any:
        """Perform an XHR request and decode the JSON answer."""
        headers = {**XHR_HEADERS, **kwargs.pop("headers", {})}
        body, final_url = await self._request(method, url, headers=headers, **kwargs)
        if "/Connexion/Login" in final_url:
            raise SievaAuthError("Session Sieva expirée")
        try:
            return json.loads(body)
        except ValueError as err:
            raise SievaParseError(f"Réponse non JSON de {url}: {body[:200]!r}") from err

    async def async_login(self) -> str:
        """Open a new authenticated session, return the landing page HTML."""
        self._session.cookie_jar.clear()
        page, _ = await self._request("GET", LOGIN_URL)
        if (match := _TOKEN_RE.search(page)) is None:
            raise SievaParseError("Jeton __RequestVerificationToken introuvable")

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
            raise SievaAuthError("Identifiants Sieva refusés")
        return body

    async def _async_get_delivery_points(
        self, landing: str
    ) -> dict[str, dict[str, str]]:
        """List the installation points of every subscription.

        The portal keeps the "current subscription" in the session: open each
        subscription page, then list its installation points.
        """
        points: dict[str, dict[str, str]] = {}
        for abonnement in parse_abonnements(landing):
            synthese = SYNTHESE_URL.format(abonnement)
            await self._request("GET", synthese)
            payload = await self._request_json(
                "POST",
                DELIVERY_POINTS_URL,
                data=DATATABLES_FORM,
                headers={"Referer": synthese},
            )
            points.update(parse_delivery_points(payload))
        return points

    async def _async_get_yearly(self, delivery_point: str) -> Any:
        """Return the raw yearly consumption of an installation point."""
        return await self._request_json(
            "POST",
            GRAPH_URL,
            json={
                "pointDInstallationId": delivery_point,
                "dateDebut": "",
                "dateFin": "",
                "granularite": "Annee",
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
                "Numéro de compteur indisponible pour %s: %s", delivery_point, err
            )
            return ""

    async def async_get_data(self) -> dict[str, SievaData]:
        """Log in once and fetch every installation point of the account."""
        landing = await self.async_login()
        points = await self._async_get_delivery_points(landing)
        _LOGGER.debug("Points d'installation trouvés: %s", points)
        data: dict[str, SievaData] = {}
        for point, info in points.items():
            raw = await self._async_get_yearly(point)
            _LOGGER.debug("GetGraphRelevesData %s: %s", point, raw)
            data[point] = SievaData(
                yearly=parse_graph_payload(raw),
                meter=await self._async_get_meter(point),
                raw=raw,
                **info,
            )
        return data

"""Look up a vehicle on DVLA's "Check if a vehicle is taxed and has an MOT" service.

DVLA isn't issuing new API keys at the moment, so this fills in the same three
pages a person would: enter the registration, confirm the vehicle, then read
the tax and MOT panels on the results page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import urljoin

import aiohttp

BASE_URL = "https://vehicleenquiry.service.gov.uk/"

USER_AGENT = "HomeAssistant-uk_vehicle_check (+https://github.com/st3nic/uk_vehicle_check)"

TIMEOUT = aiohttp.ClientTimeout(total=30)

TAX_PANEL = "tax-status-panel"
MOT_PANEL = "mot-status-panel"
ERROR_SUMMARY = "error-summary"

# Element IDs of the "Vehicle Details" rows on the results page.
DETAIL_IDS = (
    "make",
    "colour",
    "fuel_type",
    "year_of_manufacture",
    "date_of_first_registration",
    "engine_capacity",
    "co2_emissions",
)

WATCHED_IDS = {TAX_PANEL, MOT_PANEL, *DETAIL_IDS}

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "source", "track", "wbr",
}

DATE_PATTERN = re.compile(r"\b(\d{1,2} [A-Z][a-z]+ \d{4})\b")


class VehicleCheckError(Exception):
    """DVLA couldn't be reached or returned an error."""


class VehicleNotFound(VehicleCheckError):
    """DVLA has no vehicle with this registration."""


class PageChanged(VehicleCheckError):
    """DVLA's pages no longer look the way this integration expects."""


@dataclass
class VehicleData:
    registration: str
    tax_status: str | None
    tax_due: date | None
    mot_status: str | None
    mot_expiry: date | None
    checked_at: datetime
    details: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "registration": self.registration,
            "tax_status": self.tax_status,
            "tax_due": self.tax_due.isoformat() if self.tax_due else None,
            "mot_status": self.mot_status,
            "mot_expiry": self.mot_expiry.isoformat() if self.mot_expiry else None,
            "checked_at": self.checked_at.isoformat(),
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VehicleData:
        return cls(
            registration=data["registration"],
            tax_status=data.get("tax_status"),
            tax_due=date.fromisoformat(data["tax_due"]) if data.get("tax_due") else None,
            mot_status=data.get("mot_status"),
            mot_expiry=(
                date.fromisoformat(data["mot_expiry"]) if data.get("mot_expiry") else None
            ),
            checked_at=datetime.fromisoformat(data["checked_at"]),
            details=data.get("details") or {},
        )


@dataclass
class _Text:
    tag: str
    text: str
    aria_hidden: bool
    visually_hidden: bool


class _Page(HTMLParser):
    """Collects forms, the registration mark, and text inside the elements we read."""

    def __init__(self):
        super().__init__(convert_charrefs=True)

        self.forms: list[dict[str, Any]] = []
        self.sections: dict[str, list[_Text]] = {}
        self.reg_mark: str | None = None
        self._stack: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag, attrs):
        attrs = {name: value or "" for name, value in attrs}

        if tag == "form":
            self.forms.append(
                {
                    "action": attrs.get("action", ""),
                    "method": attrs.get("method", "get").lower(),
                    "inputs": [],
                }
            )
        elif tag in ("input", "button") and self.forms:
            self.forms[-1]["inputs"].append(attrs)

        if tag not in VOID_TAGS:
            self._stack.append((tag, attrs))

    def handle_endtag(self, tag):
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                break

    def handle_data(self, data):
        text = " ".join(data.split())

        if not text or not self._stack:
            return

        classes = [attrs.get("class", "").split() for _, attrs in self._stack]

        if any("reg-mark" in c for c in classes):
            self.reg_mark = text

        section = None
        for (_, attrs), element_classes in zip(reversed(self._stack), reversed(classes)):
            if attrs.get("id") in WATCHED_IDS:
                section = attrs["id"]
                break
            if "govuk-error-summary" in element_classes:
                section = ERROR_SUMMARY
                break

        if section is None:
            return

        self.sections.setdefault(section, []).append(
            _Text(
                tag=self._stack[-1][0],
                text=text,
                aria_hidden=any(a.get("aria-hidden") == "true" for _, a in self._stack),
                visually_hidden=any("govuk-visually-hidden" in c for c in classes),
            )
        )

    def main_form(self) -> dict[str, Any] | None:
        """The page's own POST form, skipping the cookie banner."""
        return next(
            (
                form
                for form in self.forms
                if form["method"] == "post" and "cookie" not in form["action"]
            ),
            None,
        )

    def section_text(self, section: str, **flags: bool) -> str:
        return " ".join(
            t.text
            for t in self.sections.get(section, [])
            if all(getattr(t, flag) == value for flag, value in flags.items())
        )


def _parse_date(text: str) -> date | None:
    if match := DATE_PATTERN.search(text):
        return datetime.strptime(match.group(1), "%d %B %Y").date()

    return None


def _strip_symbols(text: str) -> str:
    return text.strip(" ✓✔✗✘×!").strip() or None


def _mot_status(sentence: str, title: str) -> str | None:
    lowered = sentence.lower()

    if "expired" in lowered:
        return "Expired"
    if "no valid" in lowered or "not valid" in lowered or "invalid" in lowered:
        return "Not valid"
    if "valid" in lowered:
        return "Valid"
    if "no details" in lowered or "no results" in lowered or "not held" in lowered:
        return "No details held"

    # Unknown wording: show DVLA's own sentence rather than guessing.
    return re.sub(r"^Vehicle \S+ ", "", sentence).strip().capitalize() or _strip_symbols(title)


def parse_results(page: _Page, registration: str, checked_at: datetime) -> VehicleData:
    if TAX_PANEL not in page.sections or MOT_PANEL not in page.sections:
        raise PageChanged("The results page has no tax or MOT panel")

    tax_title = page.section_text(TAX_PANEL, aria_hidden=True)
    tax_sentence = page.section_text(TAX_PANEL, visually_hidden=True)
    tax_body = page.section_text(TAX_PANEL, aria_hidden=False, visually_hidden=False)

    mot_title = page.section_text(MOT_PANEL, aria_hidden=True)
    mot_sentence = page.section_text(MOT_PANEL, visually_hidden=True)
    mot_body = page.section_text(MOT_PANEL, aria_hidden=False, visually_hidden=False)

    tax_status = _strip_symbols(tax_title) or re.sub(r"^Vehicle \S+ is ", "", tax_sentence)

    details = {
        detail_id: value
        for detail_id in DETAIL_IDS
        if (value := " ".join(t.text for t in page.sections.get(detail_id, []) if t.tag == "dd"))
    }

    return VehicleData(
        registration=page.reg_mark or registration,
        tax_status=tax_status or None,
        tax_due=_parse_date(tax_body),
        mot_status=_mot_status(mot_sentence, mot_title),
        mot_expiry=_parse_date(mot_body),
        checked_at=checked_at,
        details=details,
    )


async def _request(
    session: aiohttp.ClientSession, url: str, data: dict[str, str] | None = None
) -> tuple[str, _Page]:
    method = "POST" if data is not None else "GET"

    async with session.request(method, url, data=data, timeout=TIMEOUT) as response:
        if response.status >= 400 and response.status != 422:
            raise VehicleCheckError(f"DVLA returned HTTP {response.status}")

        html = await response.text()
        final_url = str(response.url)

    page = _Page()
    page.feed(html)

    return final_url, page


def _form_data(form: dict[str, Any], values: dict[str, str]) -> dict[str, str]:
    data = {
        attrs["name"]: attrs.get("value", "")
        for attrs in form["inputs"]
        if attrs.get("name") and attrs.get("type", "text") == "hidden"
    }
    data.update(values)

    return data


async def async_lookup(
    session: aiohttp.ClientSession, registration: str, checked_at: datetime
) -> VehicleData:
    """Look up one vehicle. Makes three requests to DVLA."""
    try:
        # 1. Start page: the registration form.
        url, page = await _request(session, BASE_URL)

        form = page.main_form()
        reg_field = next(
            (
                attrs["name"]
                for attrs in (form or {}).get("inputs", [])
                if attrs.get("name") and attrs.get("type", "text") == "text"
            ),
            None,
        )

        if form is None or reg_field is None:
            raise PageChanged("No registration form on the start page")

        # 2. Submit the registration: "Is this the correct vehicle?"
        url, page = await _request(
            session, urljoin(url, form["action"]), _form_data(form, {reg_field: registration})
        )

        form = page.main_form()
        radios = [
            attrs for attrs in (form or {}).get("inputs", []) if attrs.get("type") == "radio"
        ]

        if not radios:
            if errors := page.section_text(ERROR_SUMMARY):
                raise VehicleNotFound(errors)

            raise PageChanged("No 'Is this the correct vehicle?' question")

        yes = next(
            (r for r in radios if r.get("value", "").lower().startswith("yes")), None
        )

        if yes is None:
            raise PageChanged("No 'Yes' answer on the confirm vehicle page")

        # 3. Confirm: the results page.
        url, page = await _request(
            session, urljoin(url, form["action"]), _form_data(form, {yes["name"]: yes["value"]})
        )
    except (aiohttp.ClientError, TimeoutError) as err:
        raise VehicleCheckError(f"Error communicating with DVLA: {err!r}") from err

    return parse_results(page, registration, checked_at)

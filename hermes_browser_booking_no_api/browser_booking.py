#!/usr/bin/env python3
'''
Hermes Browser Booking Harness
macOS + Google Chrome + AppleScript + Python Standard Library only.

No booking API, Selenium, Playwright, requests, pip or npm.

Security model:
- Never uses shell=True.
- User data is passed to osascript as argv, not interpolated into shell commands.
- DOM text is untrusted data and never executed as instructions.
- Final "Reserve" click only happens when commit=true.
- A state-changing final click is never blindly retried.
- CAPTCHA / authentication / unexpected page -> stop and return a structured error.
- Confirmation is only recorded if the browser page provides positive confirmation evidence.
'''

from __future__ import annotations

import dataclasses
import datetime as dt
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

MAX_INPUT = 1024 * 1024
DEFAULT_TIMEOUT = 35.0
POLL = 0.45


class HarnessError(Exception):
    code = "HARNESS_ERROR"
    def __init__(self, message: str, *, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class BrowserError(HarnessError):
    code = "BROWSER_ERROR"

class PermissionError_(HarnessError):
    code = "BROWSER_PERMISSION_REQUIRED"

class ValidationError(HarnessError):
    code = "VALIDATION_ERROR"

class TimeoutError_(HarnessError):
    code = "TIMEOUT"

class AuthRequired(HarnessError):
    code = "AUTH_REQUIRED"

class CaptchaRequired(HarnessError):
    code = "CAPTCHA_REQUIRED"

class AmbiguousUI(HarnessError):
    code = "AMBIGUOUS_UI"

class NoAvailability(HarnessError):
    code = "NO_AVAILABILITY"

class ConfirmationUnknown(HarnessError):
    code = "CONFIRMATION_UNKNOWN"


@dataclasses.dataclass(frozen=True)
class Config:
    chrome_app: str
    reservations_path: Path
    timeout_seconds: float

    @staticmethod
    def from_env() -> "Config":
        return Config(
            chrome_app=os.environ.get("HERMES_BROWSER_APP", "Google Chrome").strip(),
            reservations_path=Path(os.environ.get(
                "HERMES_RESERVATIONS_PATH",
                "~/.coffee-work/restaurant_reservations.json"
            )).expanduser(),
            timeout_seconds=float(os.environ.get(
                "HERMES_BROWSER_TIMEOUT_SECONDS",
                str(DEFAULT_TIMEOUT)
            )),
        )


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def norm_text(s: Any) -> str:
    s = str(s or "").strip().lower()
    table = str.maketrans(
        "áàâãäéèêëíìîïóòôõöúùûüçñ",
        "aaaaaeeeeiiiiooooouuuucn",
    )
    return re.sub(r"\s+", " ", s.translate(table))


def time_variants(hhmm: str) -> List[str]:
    try:
        h, m = [int(x) for x in hhmm.split(":", 1)]
    except Exception as exc:
        raise ValidationError("time must use HH:MM.") from exc
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValidationError("Invalid time.")
    variants = {f"{h:02d}:{m:02d}"}
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    variants.add(f"{h12}:{m:02d} {suffix}")
    variants.add(f"{h12}:{m:02d}{suffix}")
    variants.add(f"{h12}:{m:02d} {suffix.lower()}")
    return sorted(variants)


def date_variants(date_str: str) -> List[str]:
    try:
        d = dt.date.fromisoformat(date_str)
    except ValueError as exc:
        raise ValidationError("date must use YYYY-MM-DD.") from exc

    today = dt.date.today()
    delta = (d - today).days
    out = {
        d.isoformat(),
        d.strftime("%m/%d/%Y"),
        d.strftime("%m/%d"),
        d.strftime("%d/%m/%Y"),
        d.strftime("%d/%m"),
        d.strftime("%b %d").replace(" 0", " "),
        d.strftime("%B %d").replace(" 0", " "),
        d.strftime("%a, %b %d").replace(" 0", " "),
    }
    if delta == 0:
        out.update(["Today", "Hoje", "Hoy"])
    elif delta == 1:
        out.update(["Tomorrow", "Amanhã", "Amanha", "Mañana", "Manana"])
    return sorted(out)


APPLE_EXEC_JS = r'''
on run argv
    set jsCode to item 1 of argv
    tell application "Google Chrome"
        if not (exists front window) then error "NO_CHROME_WINDOW"
        return execute active tab of front window javascript jsCode
    end tell
end run
'''

APPLE_OPEN_URL = r'''
on run argv
    set targetURL to item 1 of argv
    tell application "Google Chrome"
        activate
        if not (exists front window) then
            make new window
        end if
        set URL of active tab of front window to targetURL
    end tell
    return "OK"
end run
'''

APPLE_GET_URL = r'''
tell application "Google Chrome"
    if not (exists front window) then error "NO_CHROME_WINDOW"
    return URL of active tab of front window
end tell
'''

JS_BASE = r'''
(() => {
  const norm = (s) => String(s || "")
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/\s+/g, " ").trim();

  const visible = (el) => {
    if (!el) return false;
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return s.visibility !== "hidden" &&
           s.display !== "none" &&
           r.width > 1 && r.height > 1;
  };

  const textOf = (el) => {
    if (!el) return "";
    return [
      el.innerText,
      el.textContent,
      el.getAttribute && el.getAttribute("aria-label"),
      el.getAttribute && el.getAttribute("title"),
      el.getAttribute && el.getAttribute("name"),
      el.getAttribute && el.getAttribute("placeholder")
    ].filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
  };

  const allRoots = () => {
    const roots = [document];
    const seen = new Set();
    const walk = (root) => {
      for (const el of root.querySelectorAll("*")) {
        if (el.shadowRoot && !seen.has(el.shadowRoot)) {
          seen.add(el.shadowRoot);
          roots.push(el.shadowRoot);
          walk(el.shadowRoot);
        }
      }
    };
    walk(document);
    return roots;
  };

  const all = (selector) => {
    const out = [];
    for (const root of allRoots()) {
      try { out.push(...root.querySelectorAll(selector)); } catch (_) {}
    }
    return out;
  };

  const candidates = () => all(
    'button,[role="button"],a,[role="option"],[role="menuitem"],' +
    '[role="radio"],[role="combobox"],select,input,[tabindex]'
  ).filter(visible);

  const exactMatch = (el, variants) => {
    const t = norm(textOf(el));
    return variants.some(v => t === norm(v));
  };

  const containsMatch = (el, variants) => {
    const t = norm(textOf(el));
    return variants.some(v => t.includes(norm(v)));
  };

  const clickBest = (variants, exactFirst=true) => {
    const c = candidates();
    let found = exactFirst ? c.find(el => exactMatch(el, variants)) : null;
    if (!found) found = c.find(el => containsMatch(el, variants));
    if (!found) return {ok:false, reason:"not_found", variants};
    found.scrollIntoView({block:"center", inline:"center"});
    found.click();
    return {
      ok:true,
      text:textOf(found),
      tag:found.tagName,
      role:found.getAttribute && found.getAttribute("role")
    };
  };

  const pageText = () => norm(document.body ? document.body.innerText : "");

  window.__HERMES = {norm, visible, textOf, all, candidates, clickBest, pageText};
  return JSON.stringify({ok:true});
})()
'''


class ChromeHarness:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def _osascript(self, script: str, args: Optional[List[str]] = None, timeout=12) -> str:
        cmd = ["/usr/bin/osascript", "-e", script]
        if args:
            cmd += ["--", *args]
        try:
            p = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BrowserError("Could not control Google Chrome.") from exc

        if p.returncode != 0:
            err = (p.stderr or p.stdout or "").strip()
            n = norm_text(err)
            if "javascript" in n and ("turned off" in n or "apple events" in n):
                raise PermissionError_(
                    "Chrome blocks JavaScript from Apple Events. Enable "
                    "'Allow JavaScript from Apple Events' in Chrome's View > Developer menu."
                )
            if "not authorized" in n or "not permitted" in n or "-1743" in n:
                raise PermissionError_(
                    "macOS automation permission is required for the process running Hermes to control Chrome."
                )
            raise BrowserError("Chrome automation failed.", details={"error": err[-800:]})
        return (p.stdout or "").strip()

    def open_url(self, url: str) -> None:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"https", "http"}:
            raise ValidationError("Only http/https browser URLs are allowed.")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValidationError("Non-local browser URLs must use HTTPS.")
        self._osascript(APPLE_OPEN_URL, [url])

    def current_url(self) -> str:
        return self._osascript(APPLE_GET_URL)

    def exec_js_raw(self, js: str) -> str:
        return self._osascript(APPLE_EXEC_JS, [js])

    def exec_json(self, js: str) -> dict:
        raw = self.exec_js_raw(js)
        try:
            val = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BrowserError(
                "Browser returned an unexpected automation result.",
                details={"raw": raw[:500]}
            ) from exc
        if not isinstance(val, dict):
            raise BrowserError("Browser returned an unexpected result shape.")
        return val

    def install_helpers(self) -> None:
        self.exec_json(JS_BASE)

    def wait_ready(self, timeout: Optional[float] = None) -> None:
        deadline = time.monotonic() + (timeout or self.cfg.timeout_seconds)
        last = None
        while time.monotonic() < deadline:
            try:
                state = self.exec_js_raw("document.readyState")
                last = state
                if state in {"interactive", "complete"}:
                    self.install_helpers()
                    return
            except HarnessError as exc:
                last = exc.message
            time.sleep(POLL)
        raise TimeoutError_(
            "Browser page did not become ready.",
            details={"last": str(last)}
        )

    def page_state(self) -> dict:
        self.install_helpers()
        js = r'''
(() => {
  const H = window.__HERMES;
  const txt = H.pageText();
  const buttonTexts = H.candidates().slice(0,80).map(H.textOf).filter(Boolean);
  const iframes = [...document.querySelectorAll("iframe")].map(x => ({
    src:x.src || "", title:x.title || "", name:x.name || ""
  }));
  return JSON.stringify({
    ok:true,
    url:location.href,
    title:document.title,
    text:txt.slice(0,12000),
    controls:buttonTexts,
    iframe_count:iframes.length,
    iframes
  });
})()
'''
        return self.exec_json(js)

    def click_text(self, variants: List[str], *, exact_first: bool = True) -> dict:
        self.install_helpers()
        payload = json.dumps(variants, ensure_ascii=False)
        js = f'''
(() => {{
  const H = window.__HERMES;
  return JSON.stringify(H.clickBest({payload}, {str(exact_first).lower()}));
}})()
'''
        return self.exec_json(js)

    def set_control_by_label(
        self,
        label_variants: List[str],
        desired_variants: List[str]
    ) -> dict:
        self.install_helpers()
        labels = json.dumps(label_variants, ensure_ascii=False)
        desired = json.dumps(desired_variants, ensure_ascii=False)
        js = f'''
(() => {{
  const H = window.__HERMES;
  const labels = {labels};
  const desired = {desired};
  const n = H.norm;

  const roots = H.all("select");
  for (const sel of roots) {{
    if (!H.visible(sel)) continue;
    let descriptor = [
      sel.getAttribute("aria-label"),
      sel.name,
      sel.id,
      sel.parentElement && H.textOf(sel.parentElement)
    ].filter(Boolean).join(" ");
    if (!labels.some(x => n(descriptor).includes(n(x)))) continue;

    const opts = [...sel.options];
    const opt = opts.find(o => desired.some(v => n(o.textContent) === n(v))) ||
                opts.find(o => desired.some(v => n(o.textContent).includes(n(v))));
    if (opt) {{
      sel.value = opt.value;
      sel.dispatchEvent(new Event("input", {{bubbles:true}}));
      sel.dispatchEvent(new Event("change", {{bubbles:true}}));
      return JSON.stringify({{ok:true, mode:"select", value:opt.textContent}});
    }}
  }}

  const cands = H.candidates();
  let trigger = null;
  for (const el of cands) {{
    const desc = [
      H.textOf(el),
      el.parentElement && H.textOf(el.parentElement),
      el.previousElementSibling && H.textOf(el.previousElementSibling)
    ].filter(Boolean).join(" ");
    if (labels.some(x => n(desc).includes(n(x)))) {{
      trigger = el; break;
    }}
  }}
  if (!trigger) return JSON.stringify({{ok:false, reason:"control_not_found", labels}});
  trigger.scrollIntoView({{block:"center"}});
  trigger.click();
  return JSON.stringify({{ok:true, mode:"opened", trigger:H.textOf(trigger)}});
}})()
'''
        first = self.exec_json(js)
        if first.get("mode") == "select":
            return first
        if not first.get("ok"):
            return first

        time.sleep(0.55)
        return self.click_text(desired_variants, exact_first=True)


def looks_like_captcha(state: dict) -> bool:
    t = norm_text(state.get("text"))
    phrases = [
        "captcha", "verify you are human", "verify that you are human",
        "unusual traffic", "nao sou um robo", "i'm not a robot",
        "soy humano", "verifique que voce e humano"
    ]
    return any(p in t for p in phrases)


def ensure_safe_state(state: dict) -> None:
    if looks_like_captcha(state):
        raise CaptchaRequired(
            "Google/provider requires human verification. Automation stopped; CAPTCHA is not bypassed."
        )
    text = norm_text(state.get("text"))
    if (
        "choose an account" in text
        or "escolha uma conta" in text
        or "use your google account" in text
    ):
        raise AuthRequired("A browser login/account selection is required.")


class ReservationStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = Path(str(path) + ".lock")

    def _ensure(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self):
        if not self.path.exists():
            return {"schema_version": 1, "reservations": []}
        try:
            obj = json.loads(self.path.read_text("utf-8"))
        except Exception as exc:
            raise HarnessError(
                "Reservation database is unreadable; no write was performed."
            ) from exc
        if not isinstance(obj, dict) or not isinstance(obj.get("reservations"), list):
            raise HarnessError("Reservation database schema is invalid.")
        return obj

    def add(self, record: dict):
        self._ensure()
        with open(self.lock, "a+", encoding="utf-8") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            obj = self._read()
            obj["reservations"].append(record)
            fd, tmp = tempfile.mkstemp(
                prefix=self.path.name + ".",
                suffix=".tmp",
                dir=str(self.path.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(obj, f, ensure_ascii=False, indent=2)
                    f.write("\n")
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)


class BookingFlow:
    RESERVE_BUTTON = [
        "Reserve a table", "Book a table", "Reserve",
        "Reservar uma mesa", "Reservar mesa",
        "Reservar una mesa", "Reservar"
    ]
    CONTINUE_BUTTON = ["Continue", "Continuar", "Siguiente", "Next"]
    FINAL_BUTTON = [
        "Reserve", "Book", "Confirm reservation",
        "Reservar", "Confirmar reserva", "Confirmar"
    ]
    PEOPLE_LABEL = [
        "People", "Guests", "Party size", "Pessoas", "Convidados", "Personas"
    ]
    DATE_LABEL = ["Date", "Data", "Fecha"]
    TIME_LABEL = ["Time", "Hora", "Horário", "Horario"]

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.browser = ChromeHarness(cfg)
        self.store = ReservationStore(cfg.reservations_path)

    def run(self, req: dict) -> dict:
        self._validate(req)
        start_url = req.get("start_url")
        query = req.get("restaurant_query")

        if start_url:
            self.browser.open_url(str(start_url))
        elif query:
            url = (
                "https://www.google.com/maps/search/"
                + urllib.parse.quote(str(query), safe="")
            )
            self.browser.open_url(url)
        else:
            raise ValidationError("start_url or restaurant_query is required.")

        self.browser.wait_ready()
        state = self.browser.page_state()
        ensure_safe_state(state)

        if "/maps/reserve/" not in state.get("url", ""):
            click = self.browser.click_text(
                self.RESERVE_BUTTON,
                exact_first=False
            )
            if not click.get("ok"):
                raise AmbiguousUI(
                    "Could not find a visible 'Reserve a table' control.",
                    details=self._diagnostic(state)
                )
            self._wait_url_or_text(
                ["/maps/reserve/"],
                self.CONTINUE_BUTTON,
                timeout=18
            )

        self.browser.wait_ready()
        state = self.browser.page_state()
        ensure_safe_state(state)

        party_size = int(req["party_size"])
        people = [str(party_size)]
        people_result = self.browser.set_control_by_label(
            self.PEOPLE_LABEL,
            people
        )
        if not people_result.get("ok"):
            people_result = self.browser.click_text(
                people,
                exact_first=True
            )
        if not people_result.get("ok"):
            raise AmbiguousUI(
                "Could not select party size safely.",
                details={
                    "party_size": party_size,
                    **self._diagnostic(self.browser.page_state())
                }
            )
        time.sleep(0.35)

        dvars = date_variants(req["date"])
        date_result = self.browser.set_control_by_label(
            self.DATE_LABEL,
            dvars
        )
        if not date_result.get("ok"):
            if not self._page_contains_any(dvars):
                raise AmbiguousUI(
                    "Could not select the requested date safely.",
                    details={
                        "date": req["date"],
                        **self._diagnostic(self.browser.page_state())
                    }
                )
        time.sleep(0.35)

        requested = time_variants(req["time"])
        selected_time = None

        tr = self.browser.click_text(requested, exact_first=True)
        if tr.get("ok"):
            selected_time = req["time"]
        else:
            tr = self.browser.set_control_by_label(
                self.TIME_LABEL,
                requested
            )
            if tr.get("ok"):
                selected_time = req["time"]

        if not selected_time:
            alternatives = self._find_nearby_times(req["time"])
            raise NoAvailability(
                "The exact time was not visible/available.",
                details={
                    "requested": req["time"],
                    "alternatives": alternatives
                }
            )

        time.sleep(0.35)
        cont = self.browser.click_text(
            self.CONTINUE_BUTTON,
            exact_first=False
        )
        if not cont.get("ok"):
            review = self.browser.page_state()
            if not self._looks_like_review(review):
                raise AmbiguousUI(
                    "Could not advance to the reservation review.",
                    details=self._diagnostic(review)
                )

        self._wait_review(timeout=15)
        review = self.browser.page_state()
        ensure_safe_state(review)

        validation = self._validate_review(review, req)
        if not validation["ok"]:
            raise AmbiguousUI(
                "Reservation review did not match the requested details. Final submit was blocked.",
                details=validation
            )

        if not req.get("commit", False):
            return {
                "ok": True,
                "status": "READY_TO_CONFIRM",
                "message": (
                    "Reservation form is ready. "
                    "Final Reserve click was not submitted."
                ),
                "review": validation["observed"],
                "url": review.get("url"),
            }

        # State-changing click. Exactly one attempt.
        final = self.browser.click_text(
            self.FINAL_BUTTON,
            exact_first=True
        )
        if not final.get("ok"):
            raise AmbiguousUI(
                "Could not identify the final Reserve button safely. Nothing was submitted.",
                details=self._diagnostic(review)
            )

        # Do not click again even if confirmation times out.
        confirmed = self._wait_confirmation(timeout=20)
        if not confirmed.get("confirmed"):
            raise ConfirmationUnknown(
                "The final Reserve button was clicked, but confirmation could not be proven. "
                "Do not retry automatically; verify in the browser/provider first.",
                details=confirmed
            )

        reservation_id = str(uuid.uuid4())
        record = {
            "reservation_id": reservation_id,
            "provider": "browser_google_reserve",
            "status": "CONFIRMED",
            "restaurant_query": req.get("restaurant_query"),
            "date": req["date"],
            "time": req["time"],
            "party_size": party_size,
            "confirmation_text": confirmed.get("evidence"),
            "confirmation_code": confirmed.get("confirmation_code"),
            "confirmation_url": confirmed.get("url"),
            "created_at": utc_now(),
        }
        self.store.add(record)

        return {
            "ok": True,
            "status": "CONFIRMED",
            "reservation": record,
            "message": "Reservation confirmed in the browser.",
        }

    def _validate(self, req: dict):
        for k in ("date", "time", "party_size"):
            if req.get(k) in ("", None):
                raise ValidationError(f"{k} is required.")
        try:
            party = int(req["party_size"])
        except Exception as exc:
            raise ValidationError(
                "party_size must be an integer."
            ) from exc
        if not 1 <= party <= 20:
            raise ValidationError(
                "party_size must be between 1 and 20."
            )
        date_variants(str(req["date"]))
        time_variants(str(req["time"]))

    def _wait_url_or_text(
        self,
        url_fragments: List[str],
        texts: List[str],
        timeout: float
    ):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            st = self.browser.page_state()
            ensure_safe_state(st)
            url = st.get("url", "")
            if any(f in url for f in url_fragments):
                return
            t = norm_text(st.get("text"))
            if any(norm_text(x) in t for x in texts):
                return
            time.sleep(POLL)
        raise TimeoutError_("Reservation page did not open.")

    def _page_contains_any(self, variants: List[str]) -> bool:
        st = self.browser.page_state()
        t = norm_text(st.get("text"))
        return any(norm_text(v) in t for v in variants)

    def _find_nearby_times(self, hhmm: str) -> List[str]:
        h, m = [int(x) for x in hhmm.split(":")]
        base = h * 60 + m
        allowed = []
        for delta in (-60, -30, 30, 60):
            x = base + delta
            if 0 <= x < 1440:
                allowed.append(f"{x//60:02d}:{x%60:02d}")

        st = self.browser.page_state()
        controls = [norm_text(x) for x in st.get("controls", [])]
        found = []
        for cand in allowed:
            if any(
                norm_text(v) in controls
                for v in time_variants(cand)
            ):
                found.append(cand)
        return found

    def _looks_like_review(self, st: dict) -> bool:
        t = norm_text(st.get("text"))
        markers = [
            "your reservation", "sua reserva", "tu reserva",
            "contact details", "dados de contato", "datos de contacto",
            "cancellation policy", "politica de cancelamento"
        ]
        return sum(m in t for m in markers) >= 1

    def _wait_review(self, timeout: float):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            st = self.browser.page_state()
            ensure_safe_state(st)
            if self._looks_like_review(st):
                return
            time.sleep(POLL)
        raise TimeoutError_("Reservation review did not appear.")

    def _validate_review(self, st: dict, req: dict) -> dict:
        t = norm_text(st.get("text"))
        party = int(req["party_size"])
        time_ok = any(
            norm_text(v) in t
            for v in time_variants(req["time"])
        )

        party_markers = [
            f"group of {party}",
            f"party of {party}",
            f"{party} guests",
            f"grupo de {party}",
            f"{party} pessoas",
            f"{party} personas"
        ]
        party_ok = any(
            norm_text(v) in t
            for v in party_markers
        )

        d = dt.date.fromisoformat(req["date"])
        date_markers = date_variants(req["date"]) + [
            f"{d.day} de {self._pt_month(d.month)}",
            f"{self._en_month(d.month)} {d.day}",
        ]
        date_ok = any(
            norm_text(v) in t
            for v in date_markers
        )

        return {
            "ok": bool(time_ok and party_ok and date_ok),
            "expected": {
                "date": req["date"],
                "time": req["time"],
                "party_size": party,
            },
            "observed": {
                "date_match": date_ok,
                "time_match": time_ok,
                "party_match": party_ok,
                "url": st.get("url"),
            }
        }

    @staticmethod
    def _pt_month(month: int) -> str:
        return [
            "", "janeiro", "fevereiro", "marco", "abril",
            "maio", "junho", "julho", "agosto", "setembro",
            "outubro", "novembro", "dezembro"
        ][month]

    @staticmethod
    def _en_month(month: int) -> str:
        return [
            "", "January", "February", "March", "April",
            "May", "June", "July", "August", "September",
            "October", "November", "December"
        ][month]

    def _wait_confirmation(self, timeout: float) -> dict:
        deadline = time.monotonic() + timeout
        last = {}
        while time.monotonic() < deadline:
            st = self.browser.page_state()
            ensure_safe_state(st)
            last = st
            t = norm_text(st.get("text"))
            positive = [
                "reservation confirmed",
                "booking confirmed",
                "your reservation is confirmed",
                "reserva confirmada",
                "sua reserva esta confirmada",
                "reserva esta confirmada",
                "confirmacion de reserva"
            ]
            if any(x in t for x in positive):
                code = self._extract_confirmation_code(
                    st.get("text", "")
                )
                return {
                    "confirmed": True,
                    "evidence": self._confirmation_excerpt(
                        st.get("text", "")
                    ),
                    "confirmation_code": code,
                    "url": st.get("url"),
                }
            time.sleep(POLL)
        return {
            "confirmed": False,
            "url": last.get("url"),
            "diagnostic": self._diagnostic(last),
        }

    @staticmethod
    def _extract_confirmation_code(text: str) -> Optional[str]:
        patterns = [
            r"(?:confirmation|confirmacao|confirmação|reserva)\s*"
            r"(?:code|codigo|código|#)?\s*[:#]?\s*([A-Z0-9-]{4,20})"
        ]
        for p in patterns:
            m = re.search(p, text, re.I)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _confirmation_excerpt(text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        return cleaned[:500]

    @staticmethod
    def _diagnostic(st: dict) -> dict:
        return {
            "url": st.get("url"),
            "title": st.get("title"),
            "controls": st.get("controls", [])[:40],
            "iframe_count": st.get("iframe_count", 0),
        }


def result_error(exc: BaseException) -> dict:
    if isinstance(exc, HarnessError):
        return {
            "ok": False,
            "code": exc.code,
            "message": exc.message,
            "details": exc.details
        }
    return {
        "ok": False,
        "code": "INTERNAL_ERROR",
        "message": (
            "Unexpected harness error. "
            "Do not assume the reservation succeeded."
        ),
    }


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise ValidationError("Input is too large.")
        try:
            req = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise ValidationError(
                "Input must be valid JSON."
            ) from exc
        if not isinstance(req, dict):
            raise ValidationError(
                "Input JSON must be an object."
            )

        flow = BookingFlow(Config.from_env())
        out = flow.run(req)
        print(json.dumps(
            out,
            ensure_ascii=False,
            separators=(",", ":")
        ))
        return 0 if out.get("ok") else 2
    except BaseException as exc:
        print(json.dumps(
            result_error(exc),
            ensure_ascii=False,
            separators=(",", ":")
        ))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

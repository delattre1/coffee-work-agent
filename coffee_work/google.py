"""Google Calendar and Drive adapter; OAuth desktop credentials are kept on the Mac."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events", "https://www.googleapis.com/auth/calendar.readonly"]
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def service(kind, version, *, home=None, interactive=False):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    home = Path(home or os.environ.get("COFFEE_HOME", "~/.coffee-work")).expanduser()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    token = home / "google-token.json"
    scopes = DRIVE_SCOPES if kind == "drive" else CALENDAR_SCOPES
    creds = Credentials.from_authorized_user_file(str(token), scopes) if token.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not interactive:
            raise RuntimeError("Google Drive authorization missing or expired. Run: coffee-work drive-auth")
        secrets = Path(os.environ.get("GOOGLE_CLIENT_SECRET_FILE", home / "google-client-secret.json")).expanduser()
        if not secrets.exists():
            raise RuntimeError(f"Google OAuth desktop client file missing: {secrets}")
        creds = InstalledAppFlow.from_client_secrets_file(str(secrets), scopes).run_local_server(port=0)
    token.write_text(creds.to_json(), encoding="utf-8")
    token.chmod(0o600)
    return build(kind, version, credentials=creds, cache_discovery=False)


class Google:
    def __init__(self, calendar_id="primary", drive_folder_id=None, *, interactive=False):
        self.calendar_id = calendar_id
        self.drive_folder_id = drive_folder_id
        self.interactive = interactive
        self._calendar = None
        self._drive = None

    @property
    def calendar(self):
        if self._calendar is None:
            self._calendar = service("calendar", "v3", interactive=self.interactive)
        return self._calendar

    @property
    def drive(self):
        if self._drive is None:
            self._drive = service("drive", "v3", interactive=self.interactive)
        return self._drive

    def upcoming(self, now=None, hours=2):
        now = now or datetime.now(timezone.utc)
        result = self.calendar.events().list(calendarId=self.calendar_id, timeMin=now.isoformat(),
            timeMax=(now + timedelta(hours=hours)).isoformat(), singleEvents=True,
            orderBy="startTime", maxResults=250).execute()
        return result.get("items", [])

    def create(self, title, start, end, location="", description="", event_type="manual", link=""):
        start_dt, end_dt = datetime.fromisoformat(start), datetime.fromisoformat(end)
        if start_dt.tzinfo is None or end_dt.tzinfo is None or end_dt <= start_dt:
            raise ValueError("Start and end must be timezone-aware, with end after start")
        body = {"summary": title, "start": {"dateTime": start}, "end": {"dateTime": end},
            "location": location, "description": description, "extendedProperties": {"private": {"coffee_work_type": event_type}}}
        if link:
            from urllib.parse import urlparse
            parsed = urlparse(link)
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError("Meeting link must be HTTPS")
            body["description"] = (description + "\n" + link).strip()
        return self.calendar.events().insert(calendarId=self.calendar_id, body=body).execute()

    def delete(self, event_id):
        event = self.calendar.events().get(calendarId=self.calendar_id, eventId=event_id).execute()
        if event.get("extendedProperties", {}).get("private", {}).get("coffee_work_type") not in ("restaurant", "coworking", "manual"):
            raise ValueError("Refusing to delete an event not created by Coffee Work")
        self.calendar.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()
        return {"deleted": event_id}

    def folder(self):
        if self.drive_folder_id:
            return self.drive_folder_id
        name = "Coffee Work Meetings"
        res = self.drive.files().list(q="name = 'Coffee Work Meetings' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            fields="files(id,name)", pageSize=100).execute().get("files", [])
        if res:
            return res[0]["id"]
        return self.drive.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.folder"}, fields="id").execute()["id"]

    def upload(self, path, folder_id=None):
        from googleapiclient.http import MediaFileUpload
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        parent = folder_id or self.folder()
        safe_name = path.name.replace("\\", "\\\\").replace("'", "\\'")
        existing = self.drive.files().list(q=f"'{parent}' in parents and name = '{safe_name}' and trashed = false",
            fields="files(id,name,webViewLink)", pageSize=100).execute().get("files", [])
        if existing:
            return existing[0]
        return self.drive.files().create(body={"name": path.name, "parents": [parent]},
            media_body=MediaFileUpload(str(path), resumable=True), fields="id,name,webViewLink").execute()

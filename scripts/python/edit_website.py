#!/usr/bin/env python3
"""Serve the CG website and save narrative text overrides locally.

This intentionally uses only Python's standard library. It binds to the
loopback interface, gives each server process a random API token, and writes
only the website's content-override files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import threading
import unicodedata
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import quote, unquote, urlsplit
import webbrowser


ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "index.html"
STATE_FILE = ROOT / "website" / "content-overrides.json"
PREVIOUS_FILE = ROOT / "website" / "content-overrides.previous.json"
JAVASCRIPT_FILE = ROOT / "website" / "content-overrides.js"

API_CONTENT = "/api/content"
API_HEALTH = "/api/health"
TOKEN_HEADER = "X-Editor-Token"
MAX_REQUEST_BYTES = 1_048_576
MAX_VALUE_CHARACTERS = 6_000
STATE_VERSION = 1
EDIT_KEY_PATTERN = re.compile(r"\bdata-edit-key\s*=\s*([\"'])([^\"']+)\1")
REVISION_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ContentError(ValueError):
    """A user-correctable content or request error."""


class RevisionConflict(ContentError):
    """The browser tried to save over a newer revision."""


def _utc_timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical_values(values: dict[str, str]) -> str:
    return json.dumps(values, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _revision(values: dict[str, str]) -> str:
    return hashlib.sha256(_canonical_values(values).encode("utf-8")).hexdigest()


def _state(values: dict[str, str], updated_at: str | None = None) -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "revision": _revision(values),
        "updated_at": updated_at,
        "values": values,
    }


def _strict_json_loads(raw: bytes) -> Any:
    def reject_constant(value: str) -> None:
        raise ContentError(f"Non-standard JSON value is not allowed: {value}")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ContentError(f"Duplicate JSON key is not allowed: {key}")
            result[key] = value
        return result

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContentError("JSON must be encoded as UTF-8.") from exc
    try:
        return json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_object)
    except json.JSONDecodeError as exc:
        raise ContentError(f"Invalid JSON: {exc.msg}") from exc


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        # These are ordinary static website assets. Keep them readable after
        # replacing them because mkstemp otherwise leaves mode 0600.
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, path)
    except BaseException:
        try:
            temporary_path.unlink(missing_ok=True)
        finally:
            raise


def _json_document(state: dict[str, Any]) -> str:
    return json.dumps(state, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def _javascript_document(values: dict[str, str]) -> str:
    # Escaping HTML-significant characters keeps this inert even if somebody
    # later decides to inline the generated assignment into an HTML document.
    serialized = _canonical_values(values)
    serialized = serialized.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return f"window.WEBSITE_CONTENT_OVERRIDES = Object.freeze({serialized});\n"


class ContentStore:
    """Validate and atomically persist the editable narrative layer."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.editable_keys = self._read_editable_keys()
        with self.lock:
            if STATE_FILE.exists():
                current = self._load_state(STATE_FILE)
            else:
                current = _state({})
                self._write_current(current)
            expected_javascript = _javascript_document(current["values"])
            if (
                not JAVASCRIPT_FILE.exists()
                or JAVASCRIPT_FILE.read_text(encoding="utf-8") != expected_javascript
            ):
                _atomic_write(JAVASCRIPT_FILE, expected_javascript)

    @staticmethod
    def _read_editable_keys() -> tuple[str, ...]:
        try:
            html = INDEX_HTML.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"Cannot read {INDEX_HTML}: {exc}") from exc
        keys = [match.group(2) for match in EDIT_KEY_PATTERN.finditer(html)]
        if not keys:
            raise RuntimeError(f"No data-edit-key attributes were found in {INDEX_HTML}.")
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise RuntimeError("Duplicate data-edit-key attributes: " + ", ".join(duplicates))
        return tuple(keys)

    def _normalize_values(self, candidate: Any) -> dict[str, str]:
        if not isinstance(candidate, dict):
            raise ContentError("values must be a JSON object.")
        if len(candidate) > len(self.editable_keys):
            raise ContentError("values contains more entries than the website exposes for editing.")

        allowed = set(self.editable_keys)
        normalized: dict[str, str] = {}
        for key, raw_value in candidate.items():
            if key not in allowed:
                raise ContentError(f"Unknown or locked text key: {key}")
            if not isinstance(raw_value, str):
                raise ContentError(f"Text for {key} must be a string.")
            if len(raw_value) > MAX_VALUE_CHARACTERS:
                raise ContentError(
                    f"Text for {key} exceeds the {MAX_VALUE_CHARACTERS:,}-character limit."
                )
            value = unicodedata.normalize("NFC", raw_value)
            for character in value:
                category = unicodedata.category(character)
                if category in {"Cs", "Co", "Cn"} or (
                    category == "Cc" and character not in {"\t", "\n", "\r"}
                ):
                    raise ContentError(f"Text for {key} contains an unsupported control character.")
            # Editable fields are deliberately single blocks of prose. This
            # removes contenteditable indentation/newlines without altering words.
            value = re.sub(r"\s+", " ", value, flags=re.UNICODE).strip()
            normalized[key] = value
        return normalized

    def _load_state(self, path: Path) -> dict[str, Any]:
        try:
            payload = _strict_json_loads(path.read_bytes())
        except OSError as exc:
            raise RuntimeError(f"Cannot read {path}: {exc}") from exc
        except ContentError as exc:
            raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"{path} must contain a JSON object.")
        if payload.get("version") != STATE_VERSION:
            raise RuntimeError(f"{path} has an unsupported version.")
        try:
            values = self._normalize_values(payload.get("values"))
        except ContentError as exc:
            raise RuntimeError(f"Invalid values in {path}: {exc}") from exc
        expected_revision = _revision(values)
        if payload.get("revision") != expected_revision:
            raise RuntimeError(f"Revision mismatch in {path}; refusing to overwrite it.")
        updated_at = payload.get("updated_at")
        if updated_at is not None and not isinstance(updated_at, str):
            raise RuntimeError(f"updated_at in {path} must be a string or null.")
        return _state(values, updated_at)

    def _write_current(self, state: dict[str, Any]) -> None:
        _atomic_write(STATE_FILE, _json_document(state))
        _atomic_write(JAVASCRIPT_FILE, _javascript_document(state["values"]))

    @staticmethod
    def _write_previous(state: dict[str, Any]) -> None:
        _atomic_write(PREVIOUS_FILE, _json_document(state))

    def public_state(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            current = state if state is not None else self._load_state(STATE_FILE)
            return {
                "version": current["version"],
                "revision": current["revision"],
                "updated_at": current["updated_at"],
                "values": dict(current["values"]),
                "editable_keys": list(self.editable_keys),
            }

    @staticmethod
    def _check_base_revision(candidate: Any, current: dict[str, Any]) -> None:
        if not isinstance(candidate, str) or not REVISION_PATTERN.fullmatch(candidate):
            raise ContentError(
                "base_revision must be the 64-character revision returned by the server."
            )
        if not hmac.compare_digest(candidate, current["revision"]):
            raise RevisionConflict("The website text changed after this editor loaded.")

    def mutate(self, request: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        allowed_request_keys = {"action", "base_revision", "values"}
        extras = sorted(set(request) - allowed_request_keys)
        if extras:
            raise ContentError("Unknown request field(s): " + ", ".join(extras))
        action = request.get("action")
        if action not in {"save", "reset", "undo"}:
            raise ContentError("action must be save, reset, or undo.")
        if action == "save" and "values" not in request:
            raise ContentError("A save request must include values.")
        if action != "save" and "values" in request:
            raise ContentError(f"A {action} request must not include values.")

        with self.lock:
            current = self._load_state(STATE_FILE)
            self._check_base_revision(request.get("base_revision"), current)

            if action == "save":
                values = self._normalize_values(request["values"])
            elif action == "reset":
                values = {}
            else:
                if not PREVIOUS_FILE.exists():
                    raise ContentError("There is no previous saved version to restore yet.")
                previous = self._load_state(PREVIOUS_FILE)
                values = previous["values"]

            if _revision(values) == current["revision"]:
                return self.public_state(current), False

            next_state = _state(values, _utc_timestamp())
            # Keeping the former current state in this slot makes Undo
            # reversible: a second Undo swaps the two saved versions again.
            self._write_previous(current)
            self._write_current(next_state)
            return self.public_state(next_state), True


class EditorHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    token: str
    store: ContentStore
    accepted_hosts: frozenset[str]
    accepted_origins: frozenset[str]


class EditorHandler(SimpleHTTPRequestHandler):
    server: EditorHTTPServer
    protocol_version = "HTTP/1.0"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _valid_host(self) -> bool:
        host = self.headers.get("Host", "").strip().lower()
        return host in self.server.accepted_hosts

    def _valid_origin(self) -> bool:
        origin = self.headers.get("Origin")
        return origin is None or origin.strip().lower() in self.server.accepted_origins

    def _valid_token(self) -> bool:
        provided = self.headers.get(TOKEN_HEADER, "")
        return bool(provided) and hmac.compare_digest(provided, self.server.token)

    @staticmethod
    def _hidden_path_requested(path: str) -> bool:
        try:
            decoded = unquote(path, encoding="utf-8", errors="strict")
        except UnicodeDecodeError:
            return True
        return any(
            part.startswith(".")
            for part in decoded.replace("\\", "/").split("/")
            if part
        )

    def _reject_hidden_static_path(self, path: str) -> bool:
        if not self._hidden_path_requested(path):
            return False
        self._send_json(
            HTTPStatus.FORBIDDEN,
            {"error": "hidden_path", "message": "Hidden files and folders are not served."},
        )
        return True

    def _send_json(self, status: HTTPStatus | int, payload: dict[str, Any]) -> None:
        encoded = (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(encoded)

    def _reject_invalid_host(self) -> bool:
        if self._valid_host():
            return False
        self._send_json(
            HTTPStatus.BAD_REQUEST,
            {"error": "invalid_host", "message": "Invalid Host header."},
        )
        return True

    def _authorize_api(self) -> bool:
        if self._reject_invalid_host():
            return False
        if not self._valid_origin():
            self._send_json(
                HTTPStatus.FORBIDDEN,
                {
                    "error": "invalid_origin",
                    "message": "The editor API accepts same-origin requests only.",
                },
            )
            return False
        if not self._valid_token():
            self._send_json(
                HTTPStatus.FORBIDDEN,
                {
                    "error": "invalid_token",
                    "message": f"Missing or invalid {TOKEN_HEADER} header.",
                },
            )
            return False
        return True

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if self._reject_invalid_host():
            return
        if path == "/":
            destination = f"/editor.html?token={quote(self.server.token, safe='')}"
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", destination)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == API_HEALTH:
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "editable_key_count": len(self.server.store.editable_keys),
                },
            )
            return
        if path == API_CONTENT:
            if not self._authorize_api():
                return
            try:
                payload = self.server.store.public_state()
            except (RuntimeError, OSError) as exc:
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "state_error", "message": str(exc)},
                )
                return
            self._send_json(HTTPStatus.OK, payload)
            return
        if self._reject_hidden_static_path(path):
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        path = urlsplit(self.path).path
        if self._reject_invalid_host():
            return
        if path == API_CONTENT:
            if self._authorize_api():
                self._send_json(
                    HTTPStatus.METHOD_NOT_ALLOWED,
                    {"error": "method_not_allowed"},
                )
            return
        if path == API_HEALTH:
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if path == "/":
            destination = f"/editor.html?token={quote(self.server.token, safe='')}"
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", destination)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self._reject_hidden_static_path(path):
            return
        super().do_HEAD()

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path != API_CONTENT:
            if self._reject_invalid_host():
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self._authorize_api():
            return

        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._send_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                {
                    "error": "content_type",
                    "message": "Content-Type must be application/json.",
                },
            )
            return
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            self._send_json(
                HTTPStatus.LENGTH_REQUIRED,
                {"error": "length_required", "message": "Content-Length is required."},
            )
            return
        try:
            length = int(raw_length, 10)
        except ValueError:
            length = -1
        if length < 0:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_length"})
            return
        if length > MAX_REQUEST_BYTES:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": "request_too_large", "message": "The JSON request exceeds 1 MiB."},
            )
            return
        raw = self.rfile.read(length)
        if len(raw) != length:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "incomplete_request"})
            return
        try:
            request = _strict_json_loads(raw)
            if not isinstance(request, dict):
                raise ContentError("The request body must be a JSON object.")
            action = request.get("action")
            state, changed = self.server.store.mutate(request)
        except RevisionConflict as exc:
            current = self.server.store.public_state()
            self._send_json(
                409,
                {
                    "error": "revision_conflict",
                    "message": str(exc),
                    "current_revision": current["revision"],
                    "state": current,
                },
            )
            return
        except ContentError as exc:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid_request", "message": str(exc)},
            )
            return
        except (RuntimeError, OSError) as exc:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "state_error", "message": str(exc)},
            )
            return
        state.update({"action": action, "changed": changed})
        self._send_json(HTTPStatus.OK, state)

    def do_OPTIONS(self) -> None:
        # Deliberately omit CORS headers. Browser requests must originate from
        # this local server and carry the per-process token.
        if self._reject_invalid_host():
            return
        self._send_json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method_not_allowed"})

    def list_directory(self, path: str) -> None:
        self.send_error(HTTPStatus.FORBIDDEN, "Directory listing is disabled")
        return None

    def translate_path(self, path: str) -> str:
        candidate = Path(super().translate_path(path)).resolve()
        root = ROOT.resolve()
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            return str(root / ".editor-access-denied")
        if any(part.startswith(".") for part in relative.parts):
            return str(root / ".editor-access-denied")
        return str(candidate)

    def log_message(self, format: str, *args: Any) -> None:
        # Keep the terminal useful: report API writes/errors, not every asset.
        path = urlsplit(self.path).path
        status = str(args[1]) if len(args) > 1 else ""
        if (
            self.command == "POST"
            or path.startswith("/api/")
            or (status and not status.startswith(("2", "3")))
        ):
            super().log_message(format, *args)


def _port(value: str) -> int:
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 0 <= parsed <= 65_535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return parsed


def _build_server(requested_port: int, token: str, store: ContentStore) -> EditorHTTPServer:
    try:
        server = EditorHTTPServer(("127.0.0.1", requested_port), EditorHandler)
    except OSError:
        if requested_port == 0:
            raise
        print(
            f"Port {requested_port} is unavailable; choosing a free local port instead.",
            flush=True,
        )
        server = EditorHTTPServer(("127.0.0.1", 0), EditorHandler)

    actual_port = int(server.server_address[1])
    server.token = token
    server.store = store
    server.accepted_hosts = frozenset(
        {f"127.0.0.1:{actual_port}", f"localhost:{actual_port}"}
    )
    server.accepted_origins = frozenset(
        {f"http://127.0.0.1:{actual_port}", f"http://localhost:{actual_port}"}
    )
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Open the Conservation Genomics website's local text editor."
    )
    parser.add_argument("--port", type=_port, default=8765, help="local port (default: 8765)")
    parser.add_argument("--no-open", action="store_true", help="do not open the browser automatically")
    args = parser.parse_args(argv)

    try:
        store = ContentStore()
        token = secrets.token_urlsafe(32)
        server = _build_server(args.port, token, store)
    except (RuntimeError, OSError) as exc:
        print(f"Could not start the website editor: {exc}", file=sys.stderr)
        return 1

    port = int(server.server_address[1])
    editor_url = f"http://127.0.0.1:{port}/editor.html?token={quote(token, safe='')}"
    print("\nConservation Genomics website editor", flush=True)
    print(f"Open: {editor_url}", flush=True)
    print("Keep this window open while editing. Press Control-C here to stop.\n", flush=True)

    if not args.no_open:
        try:
            opened = webbrowser.open(editor_url, new=2)
            if not opened:
                print(
                    "The browser did not open automatically; copy the Open address above.",
                    flush=True,
                )
        except webbrowser.Error:
            print(
                "The browser did not open automatically; copy the Open address above.",
                flush=True,
            )

    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nStopping the website editor.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

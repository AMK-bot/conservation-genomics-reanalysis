#!/usr/bin/env python3
"""Build and verify a deterministic, self-contained project-website ZIP."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from html.parser import HTMLParser
import io
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit
import zipfile


ARCHIVE_FOLDER = "conservation-genomics-portfolio"
DEFAULT_ARCHIVE = "dist/conservation-genomics-portfolio.zip"
DEFAULT_REPORT = "results/WEBSITE_BUNDLE_VALIDATION.md"
FIXED_ZIP_TIME = (2026, 7, 18, 0, 0, 0)
RUNTIME_TAGS = {"script", "link", "img", "source", "video", "audio", "css"}
EXTRA_FILES = {
    ".nojekyll",
    "requirements.txt",
    "scripts/python/validate_website.py",
}
PORTABLE_SOURCE_FILES = {
    ".gitignore",
    ".Rprofile",
    "admissions/brief.css",
    "data/README.md",
    "environment.yml",
    "renv/.gitignore",
    "renv/activate.R",
    "renv/settings.json",
}
PORTABLE_SOURCE_DIRECTORIES = {
    "config",
    "report",
    "scripts",
    "workflow",
}
EXECUTABLE_FILES = {
    "report/render_report.sh",
    "report/report_values.py",
    "scripts/build_tools.sh",
    "scripts/extract_data.sh",
    "scripts/fetch_data.sh",
    "scripts/filter_preset.sh",
}
IGNORED_SOURCE_PARTS = {"__pycache__", ".DS_Store"}
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)


class BundleError(RuntimeError):
    """Raised when the site cannot be packaged safely or completely."""


@dataclass(frozen=True)
class Reference:
    source: str
    tag: str
    value: str


@dataclass(frozen=True)
class LocalReference:
    source: str
    target: str
    fragment: str


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class Collection:
    files: set[str]
    entry_targets: set[str]
    local_references: list[LocalReference]
    external_runtime: list[Reference]


class ReferenceParser(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.references: list[Reference] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if identifier := values.get("id"):
            self.ids.add(identifier)
        for attribute in ("href", "xlink:href", "src"):
            if value := values.get(attribute):
                self.references.append(Reference(self.source, tag, value))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--html", default="index.html", help="Website entry point")
    parser.add_argument("--out", default=DEFAULT_ARCHIVE, help="Output ZIP path")
    parser.add_argument("--report", default=DEFAULT_REPORT, help="Validation report path")
    parser.add_argument("--folder", default=ARCHIVE_FOLDER, help="Top-level folder inside ZIP")
    return parser.parse_args()


def html_references(path: Path, relative: str) -> tuple[list[Reference], set[str]]:
    parser = ReferenceParser(relative)
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.references, parser.ids


def css_references(path: Path, relative: str) -> list[Reference]:
    text = path.read_text(encoding="utf-8")
    return [Reference(relative, "css", match.group(2)) for match in CSS_URL.finditer(text)]


def ensure_within_root(root: Path, source: str, path_text: str) -> tuple[Path, str]:
    decoded = unquote(path_text)
    if decoded.startswith("/"):
        candidate = root / decoded.lstrip("/")
    else:
        candidate = root / Path(source).parent / decoded
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise BundleError(f"Reference escapes repository: {source} -> {path_text}") from exc
    return resolved, relative.as_posix()


def has_symlink_component(root: Path, relative: str) -> bool:
    current = root
    for component in PurePosixPath(relative).parts:
        current = current / component
        if current.is_symlink():
            return True
    return False


def classify_reference(root: Path, reference: Reference) -> tuple[str | None, str]:
    value = reference.value.strip()
    if not value or value.startswith("//"):
        return None, ""
    parsed = urlsplit(value)
    if parsed.scheme:
        return None, unquote(parsed.fragment)
    if not parsed.path:
        return reference.source, unquote(parsed.fragment)
    target_path, target_relative = ensure_within_root(root, reference.source, parsed.path)
    if not target_path.is_file():
        raise BundleError(f"Missing local target: {reference.source} -> {reference.value}")
    if has_symlink_component(root, target_relative):
        raise BundleError(f"Symlink-backed target is not portable: {target_relative}")
    return target_relative, unquote(parsed.fragment)


def collect_files(root: Path, entry: str) -> Collection:
    entry_path = (root / entry).resolve()
    if not entry_path.is_file():
        raise BundleError(f"Missing website entry point: {entry_path}")
    try:
        entry_relative = entry_path.relative_to(root).as_posix()
    except ValueError as exc:
        raise BundleError("Website entry point is outside the repository") from exc

    files: set[str] = set()
    entry_targets: set[str] = set()
    local_references: list[LocalReference] = []
    external_runtime: list[Reference] = []
    queue = [entry_relative]

    while queue:
        relative = queue.pop()
        if relative in files:
            continue
        path = root / relative
        if not path.is_file():
            raise BundleError(f"Missing bundle source: {relative}")
        if has_symlink_component(root, relative):
            raise BundleError(f"Symlink-backed source is not portable: {relative}")
        files.add(relative)

        suffix = path.suffix.lower()
        if suffix in {".html", ".htm", ".svg"}:
            references, _ids = html_references(path, relative)
        elif suffix == ".css":
            references = css_references(path, relative)
        else:
            references = []

        for reference in references:
            parsed = urlsplit(reference.value.strip())
            if parsed.scheme or reference.value.startswith("//"):
                if reference.tag in RUNTIME_TAGS and parsed.scheme not in {"data"}:
                    external_runtime.append(reference)
                continue
            target, fragment = classify_reference(root, reference)
            if target is None:
                continue
            local_references.append(LocalReference(relative, target, fragment))
            if relative == entry_relative and target != entry_relative:
                entry_targets.add(target)
            if target not in files:
                queue.append(target)

    portable_sources = set(PORTABLE_SOURCE_FILES)
    for directory in sorted(PORTABLE_SOURCE_DIRECTORIES):
        directory_path = root / directory
        if not directory_path.is_dir():
            raise BundleError(f"Missing portable source directory: {directory}")
        for path in directory_path.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            if any(part in IGNORED_SOURCE_PARTS for part in path.parts) or path.suffix == ".pyc":
                continue
            portable_sources.add(relative)

    for relative in sorted(EXTRA_FILES | portable_sources):
        path = root / relative
        if not path.is_file():
            raise BundleError(f"Missing required bundle support file: {relative}")
        if has_symlink_component(root, relative):
            raise BundleError(f"Symlink-backed support file is not portable: {relative}")
        files.add(relative)

    if external_runtime:
        detail = "; ".join(f"{ref.source}: {ref.value}" for ref in external_runtime[:8])
        raise BundleError(f"External runtime dependencies prevent an offline bundle: {detail}")

    return Collection(files, entry_targets, local_references, external_runtime)


def case_collisions(paths: set[str]) -> list[str]:
    groups: dict[str, list[str]] = {}
    for path in paths:
        groups.setdefault(path.casefold(), []).append(path)
    return [", ".join(sorted(group)) for group in groups.values() if len(group) > 1]


def recipient_readme(entry_targets: int, source_files: int) -> bytes:
    text = f"""CONSERVATION GENOMICS PROJECT PORTFOLIO
========================================

START HERE
----------
1. Extract this entire ZIP archive. Do not open index.html from inside the ZIP.
2. Open index.html in any modern web browser.
3. No installation or internet connection is required for the website itself.

WHAT IS INCLUDED
----------------
- The complete offline project website and all {entry_targets} local targets it links to.
- All static CSS, JavaScript, figures, screenshots, reports, tables, validation records,
  project documentation, and the precomputed files used by the optional explorer app.
- {source_files} project files in total, plus this guide and MANIFEST.sha256.

For browsing this portfolio, internet access is needed only for external citation links. A fresh
reanalysis also needs network access to obtain the cited public datasets and tool sources.

OPTIONAL LOCAL SERVER
---------------------
Directly opening index.html works. For a hosting-style preview, run this command inside the
extracted conservation-genomics-portfolio folder:

    python -m http.server 8000

Then open http://localhost:8000/.

OPTIONAL EXPLORER APP
---------------------
The website is static and does not require Python packages. To run the separate Streamlit
explorer, install requirements.txt in an isolated environment and then run:

    python -m streamlit run app/streamlit_app.py

PACKAGE SCOPE
-------------
This is the sendable offline portfolio and its linked deliverables. Large public raw genomic
datasets and regenerable analysis intermediates are intentionally excluded because they are not
website dependencies. The included workflow and configuration files document reproducibility;
a complete reanalysis additionally requires the public datasets cited in the website and the
setup described in SETUP.md.

INTEGRITY
---------
MANIFEST.sha256 records the SHA-256 digest of every other file in this folder.
"""
    return text.encode("utf-8")


def source_payload(root: Path, collection: Collection) -> dict[str, bytes]:
    payload = {relative: (root / relative).read_bytes() for relative in collection.files}
    payload["README_FIRST.txt"] = recipient_readme(
        len(collection.entry_targets), len(collection.files)
    )
    collisions = case_collisions(set(payload))
    if collisions:
        raise BundleError(f"Case-insensitive filename collision: {'; '.join(collisions)}")
    manifest_rows = [
        f"{hashlib.sha256(payload[path]).hexdigest()}  {path}"
        for path in sorted(payload)
    ]
    payload["MANIFEST.sha256"] = ("\n".join(manifest_rows) + "\n").encode("utf-8")
    return payload


def zip_bytes(payload: dict[str, bytes], folder: str) -> bytes:
    if not folder or "/" in folder or "\\" in folder or folder in {".", ".."}:
        raise BundleError(f"Unsafe archive folder name: {folder!r}")
    stream = io.BytesIO()
    with zipfile.ZipFile(
        stream, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for relative in sorted(payload):
            info = zipfile.ZipInfo(f"{folder}/{relative}", date_time=FIXED_ZIP_TIME)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o100755 if relative in EXECUTABLE_FILES else 0o100644
            info.external_attr = mode << 16
            archive.writestr(info, payload[relative])
    return stream.getvalue()


def write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    path.chmod(0o644)


def safe_archive_names(infos: list[zipfile.ZipInfo], folder: str) -> tuple[bool, str]:
    names = [info.filename for info in infos]
    issues: list[str] = []
    if len(names) != len(set(names)):
        issues.append("duplicate member names")
    if len({name.casefold() for name in names}) != len(names):
        issues.append("case-insensitive member collision")
    for info in infos:
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts or "\\" in info.filename:
            issues.append(f"unsafe path {info.filename}")
        if not path.parts or path.parts[0] != folder:
            issues.append(f"member outside root folder {info.filename}")
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            issues.append(f"symlink member {info.filename}")
    return not issues, "portable member paths and modes" if not issues else "; ".join(issues[:8])


def verify_manifest(
    archive: zipfile.ZipFile, payload: dict[str, bytes], folder: str
) -> tuple[bool, str]:
    manifest_name = f"{folder}/MANIFEST.sha256"
    rows = archive.read(manifest_name).decode("utf-8").splitlines()
    recorded: dict[str, str] = {}
    for row in rows:
        digest, separator, relative = row.partition("  ")
        if not separator or len(digest) != 64 or relative in recorded:
            return False, f"malformed manifest row: {row[:80]}"
        recorded[relative] = digest
    expected = set(payload) - {"MANIFEST.sha256"}
    if set(recorded) != expected:
        missing = sorted(expected - set(recorded))
        extra = sorted(set(recorded) - expected)
        return False, f"manifest coverage mismatch; missing={missing[:4]}, extra={extra[:4]}"
    for relative, expected_digest in recorded.items():
        actual = hashlib.sha256(archive.read(f"{folder}/{relative}")).hexdigest()
        if actual != expected_digest:
            return False, f"hash mismatch: {relative}"
    return True, f"all {len(recorded)} non-manifest members match SHA-256"


def verify_executable_modes(
    infos: list[zipfile.ZipInfo], payload: dict[str, bytes], folder: str
) -> tuple[bool, str]:
    expected = {
        f"{folder}/{relative}" for relative in EXECUTABLE_FILES if relative in payload
    }
    actual = {
        info.filename
        for info in infos
        if ((info.external_attr >> 16) & 0o111) != 0
    }
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        return False, f"executable mode mismatch; missing={missing}, extra={extra}"
    return True, f"all {len(expected)} runnable source scripts retain mode 0755"


def validate_fragments(root: Path, references: list[LocalReference]) -> tuple[bool, str]:
    id_cache: dict[str, set[str]] = {}
    checked = 0
    missing: list[str] = []
    for reference in references:
        if not reference.fragment or Path(reference.target).suffix.lower() not in {".html", ".htm"}:
            continue
        if reference.target not in id_cache:
            _references, ids = html_references(root / reference.target, reference.target)
            id_cache[reference.target] = ids
        checked += 1
        if reference.fragment not in id_cache[reference.target]:
            missing.append(f"{reference.target}#{reference.fragment}")
    return (
        not missing,
        f"{checked} HTML fragment links checked" if not missing else f"missing: {', '.join(missing[:8])}",
    )


def extracted_website_validation(extracted_root: Path, temporary: Path) -> tuple[bool, str]:
    report = temporary / "extracted-website-validation.md"
    command = [
        sys.executable,
        str(extracted_root / "scripts/python/validate_website.py"),
        "--root",
        str(extracted_root),
        "--html",
        "index.html",
        "--out",
        str(report),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    text = report.read_text(encoding="utf-8") if report.is_file() else ""
    ok = completed.returncode == 0 and "**Summary: 10 PASS, 0 FAIL**" in text
    detail = "10 PASS, 0 FAIL after fresh extraction" if ok else (
        completed.stdout + completed.stderr
    ).strip()[-500:]
    return ok, detail or "validation report was not produced"


def verify_bundle(
    archive_content: bytes,
    payload: dict[str, bytes],
    folder: str,
    collection: Collection,
) -> list[Check]:
    checks: list[Check] = []
    with zipfile.ZipFile(io.BytesIO(archive_content), "r") as archive:
        bad_member = archive.testzip()
        checks.append(
            Check(
                "ZIP integrity",
                bad_member is None,
                "all compressed members pass CRC" if bad_member is None else f"CRC failure: {bad_member}",
            )
        )
        safe, safe_detail = safe_archive_names(archive.infolist(), folder)
        checks.append(Check("safe portable archive paths", safe, safe_detail))
        modes_ok, modes_detail = verify_executable_modes(archive.infolist(), payload, folder)
        checks.append(Check("portable executable modes", modes_ok, modes_detail))
        manifest_ok, manifest_detail = verify_manifest(archive, payload, folder)
        checks.append(Check("exact SHA-256 manifest", manifest_ok, manifest_detail))

        if safe and bad_member is None:
            with tempfile.TemporaryDirectory(prefix="cg-website-bundle-") as temporary_name:
                temporary = Path(temporary_name)
                archive.extractall(temporary)
                extracted_root = temporary / folder
                entry_ok = (extracted_root / "index.html").is_file()
                checks.append(
                    Check(
                        "fresh extraction",
                        entry_ok,
                        f"{folder}/index.html is ready to open" if entry_ok else "entry point missing",
                    )
                )
                fragments_ok, fragments_detail = validate_fragments(
                    extracted_root, collection.local_references
                )
                checks.append(Check("cross-file HTML anchors", fragments_ok, fragments_detail))
                validator_ok, validator_detail = extracted_website_validation(extracted_root, temporary)
                checks.append(
                    Check("extracted website validation", validator_ok, validator_detail)
                )
        else:
            checks.extend(
                [
                    Check("fresh extraction", False, "skipped because archive safety failed"),
                    Check("cross-file HTML anchors", False, "skipped because archive safety failed"),
                    Check("extracted website validation", False, "skipped because archive safety failed"),
                ]
            )
    return checks


def validation_report(
    checks: list[Check],
    archive_path: Path,
    archive_content: bytes,
    collection: Collection,
    payload: dict[str, bytes],
) -> str:
    passed = sum(check.ok for check in checks)
    failed = len(checks) - passed
    digest = hashlib.sha256(archive_content).hexdigest()
    rows = [
        "# Sendable website bundle validation",
        "",
        "The project portfolio is packaged as one deterministic ZIP with its complete local link closure.",
        "",
        f"**Summary: {passed} PASS, {failed} FAIL**",
        "",
        "| check | status | evidence |",
        "|---|---|---|",
    ]
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        detail = check.detail.replace("|", "\\|").replace("\n", " ")
        rows.append(f"| {check.name} | **{status}** | {detail} |")
    rows.extend(
        [
            "",
            "## Bundle",
            "",
            f"- Archive: `{archive_path.as_posix()}`",
            f"- Compressed size: {len(archive_content):,} bytes",
            f"- ZIP entries: {len(payload):,}",
            f"- Bundled project files: {len(collection.files):,}",
            f"- Website-local targets: {len(collection.entry_targets):,}",
            f"- SHA-256: `{digest}`",
            "",
            "The bundle excludes raw public genomic datasets and regenerable intermediates; these are not",
            "website dependencies. External DOI citations require internet only when opened.",
            "",
        ]
    )
    return "\n".join(rows)


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    archive_path = Path(args.out)
    if not archive_path.is_absolute():
        archive_path = root / archive_path
    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = root / report_path

    try:
        collection = collect_files(root, args.html)
        payload = source_payload(root, collection)
        first = zip_bytes(payload, args.folder)
        second = zip_bytes(payload, args.folder)
        deterministic = first == second
        checks = [
            Check(
                "complete website dependency closure",
                len(collection.entry_targets) > 0,
                f"{len(collection.entry_targets)} local website targets; {len(collection.files)} project files",
            ),
            Check(
                "no external runtime dependency",
                not collection.external_runtime,
                "all CSS, JavaScript, fonts, images, and embedded report assets are local",
            ),
            Check(
                "deterministic construction",
                deterministic,
                "two independent in-memory builds are byte-identical" if deterministic else "builds differ",
            ),
        ]
        checks.extend(verify_bundle(first, payload, args.folder, collection))
        try:
            archive_display = archive_path.relative_to(root)
        except ValueError:
            archive_display = archive_path
        report_text = validation_report(checks, archive_display, first, collection, payload)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")
        if not all(check.ok for check in checks):
            print(report_text, file=sys.stderr)
            raise SystemExit(1)
        write_atomic(archive_path, first)
    except BundleError as exc:
        print(f"Website bundle error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    digest = hashlib.sha256(first).hexdigest()
    print(f"Website bundle: {archive_path}")
    print(f"Project files: {len(collection.files)}; entries: {len(payload)}")
    print(f"Size: {len(first):,} bytes; SHA-256: {digest}")
    print(f"Validation: {sum(check.ok for check in checks)} PASS, 0 FAIL")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

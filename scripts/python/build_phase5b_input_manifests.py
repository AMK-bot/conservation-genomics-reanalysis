#!/usr/bin/env python3
"""Build deterministic Phase-5B byte manifests for exact input path lists.

Each output is a two-column TSV (``path``, ``file_sha256``) sorted by path.
The aggregate digest printed by this program is SHA-256 over standard
``sha256sum``-style records::

    <file_sha256><two spaces><path><newline>

The header is deliberately excluded from the aggregate.  Inputs may be
repository-relative symlinks to externally stored source data; paths are
validated lexically and the bytes reached through those exact paths are hashed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
from pathlib import Path, PurePosixPath
import tempfile


ROOT = Path(__file__).resolve().parents[2]
TSV_COLUMNS = ("path", "file_sha256")


class ManifestBuildError(RuntimeError):
    """One fail-closed manifest construction error."""


def safe_relative_path(value: str, label: str) -> str:
    """Return one canonical, lexical repository-relative POSIX path."""
    if not value or "\\" in value:
        raise ManifestBuildError(f"{label} is not a safe relative path: {value!r}")
    pure = PurePosixPath(value)
    canonical = pure.as_posix()
    if pure.is_absolute() or ".." in pure.parts or canonical in ("", "."):
        raise ManifestBuildError(f"{label} is not a safe relative path: {value!r}")
    if value != canonical:
        raise ManifestBuildError(f"{label} is not canonical: {value!r} != {canonical!r}")
    return canonical


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def records_for_paths(root: Path, paths: list[str], label: str) -> list[tuple[str, str]]:
    canonical = [safe_relative_path(value, f"{label} input") for value in paths]
    if len(canonical) != len(set(canonical)):
        duplicates = sorted({value for value in canonical if canonical.count(value) > 1})
        raise ManifestBuildError(f"{label} inputs contain duplicate paths: {duplicates}")
    records: list[tuple[str, str]] = []
    for relative in sorted(canonical):
        target = root / relative
        if not target.is_file():
            raise ManifestBuildError(f"{label} input is not a file: {relative}")
        records.append((relative, sha256_file(target)))
    return records


def aggregate_sha256(records: list[tuple[str, str]]) -> str:
    payload = "".join(
        f"{file_sha256}  {path}\n" for path, file_sha256 in sorted(records)
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def output_path(root: Path, value: str | Path) -> Path:
    candidate = Path(value)
    path = candidate if candidate.is_absolute() else root / candidate
    resolved_root = root.resolve()
    resolved_parent = path.parent.resolve()
    try:
        resolved_parent.relative_to(resolved_root)
    except ValueError as error:
        raise ManifestBuildError(f"manifest output escapes repository root: {path}") from error
    return path


def write_manifest(path: Path, records: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(TSV_COLUMNS)
            writer.writerows(sorted(records))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def build_one(
    root: Path, paths: list[str], output: str | Path, label: str
) -> tuple[int, str]:
    records = records_for_paths(root, paths, label)
    write_manifest(output_path(root, output), records)
    return len(records), aggregate_sha256(records)


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="cg-phase5b-input-manifests-") as temporary:
        root = Path(temporary)
        for relative, payload in (("z/source.bin", b"z\n"), ("a/source.bin", b"a\n")):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

        output = "results/provenance/test.tsv"
        count, digest = build_one(
            root, ["z/source.bin", "a/source.bin"], output, "synthetic"
        )
        expected_records = [
            ("a/source.bin", sha256_file(root / "a/source.bin")),
            ("z/source.bin", sha256_file(root / "z/source.bin")),
        ]
        assert count == 2
        assert digest == aggregate_sha256(expected_records)
        assert (root / output).read_text(encoding="utf-8").splitlines() == [
            "path\tfile_sha256",
            *(f"{path}\t{file_sha256}" for path, file_sha256 in expected_records),
        ]
        try:
            records_for_paths(root, ["a/source.bin", "a/source.bin"], "duplicates")
        except ManifestBuildError:
            pass
        else:
            raise AssertionError("duplicate paths must fail closed")
        try:
            records_for_paths(root, ["../escape"], "escape")
        except ManifestBuildError:
            pass
        else:
            raise AssertionError("escaping paths must fail closed")
    print("build_phase5b_input_manifests self-test: OK")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="repository root")
    parser.add_argument("--frozen-inputs", nargs="+", help="exact frozen-upstream paths")
    parser.add_argument("--external-inputs", nargs="+", help="exact external-source paths")
    parser.add_argument("--out-frozen", help="frozen-upstream manifest TSV")
    parser.add_argument("--out-external", help="external-source manifest TSV")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    required = {
        "--frozen-inputs": args.frozen_inputs,
        "--external-inputs": args.external_inputs,
        "--out-frozen": args.out_frozen,
        "--out-external": args.out_external,
    }
    missing = [flag for flag, value in required.items() if not value]
    if missing:
        raise ManifestBuildError(f"missing required arguments: {missing}")

    root = Path(args.root).resolve()
    frozen_count, frozen_digest = build_one(
        root, args.frozen_inputs, args.out_frozen, "frozen_upstream_inputs"
    )
    external_count, external_digest = build_one(
        root, args.external_inputs, args.out_external, "external_source_leaves"
    )
    print(f"frozen_upstream_inputs\t{frozen_count}\t{frozen_digest}")
    print(f"external_source_leaves\t{external_count}\t{external_digest}")


if __name__ == "__main__":
    main()

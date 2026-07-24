#!/usr/bin/env python3
"""Run a command while recording peak RSS for its complete process tree.

The target's stdout and stderr are combined in one log.  A JSON sidecar records
timing, command status, and the largest sum of resident-set sizes observed for
the target process and all descendants present in each ``ps`` snapshot.

Example::

    python scripts/python/run_with_rss.py --json /tmp/check.json --log /tmp/check.log -- python -m unittest

Only the Python standard library and a POSIX ``ps`` implementation are needed.
The wrapper exits with the target's status, with 125 reserved for monitoring
failures.  Run ``--self-test`` for a deterministic, offline end-to-end check.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO, Dict, List, Mapping, Optional, Sequence, Tuple


DEFAULT_INTERVAL_SECONDS = 0.25
MAX_INTERVAL_SECONDS = 1.0
PS_TIMEOUT_SECONDS = 1.0
SAMPLING_FAILURE_EXIT = 125
LAUNCH_FAILURE_EXIT = 126
COMMAND_NOT_FOUND_EXIT = 127


class SamplingUnavailable(RuntimeError):
    """Raised when a trustworthy process-tree RSS sample cannot be obtained."""


class RootProcessGone(RuntimeError):
    """Raised when the monitored root has left a valid process snapshot."""


@dataclass(frozen=True)
class TreeSample:
    rss_kib: int
    process_count: int


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _derive_monotonic_end(
    start_time_utc: str,
    elapsed_seconds: float,
    observed_end_time_utc: str,
) -> tuple[str, float]:
    """Return a clock-jump-safe end timestamp plus observed wall-clock drift.

    The duration comes from ``time.monotonic()``.  Anchoring that duration to
    the launch timestamp keeps the reported interval internally consistent if
    macOS corrects its wall clock while a long command is running.  The raw
    observed end is retained separately so the adjustment remains auditable.
    """

    start = datetime.fromisoformat(start_time_utc.replace("Z", "+00:00"))
    observed_end = datetime.fromisoformat(
        observed_end_time_utc.replace("Z", "+00:00")
    )
    derived_end = start + timedelta(seconds=elapsed_seconds)
    drift_seconds = (observed_end - start).total_seconds() - elapsed_seconds
    return (
        derived_end.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        round(drift_seconds, 6),
    )


def _signal_name(signum: int) -> str:
    try:
        return signal.Signals(signum).name
    except ValueError:
        return str(signum)


def _normalise_exit_code(return_code: int) -> int:
    """Convert subprocess' negative signal convention to a shell exit status."""

    return 128 + (-return_code) if return_code < 0 else return_code


class ProcessSampler:
    """Take portable macOS/Linux process snapshots using ``ps``."""

    def __init__(self) -> None:
        executable = shutil.which("ps")
        if executable is None:
            raise SamplingUnavailable("ps is not available on PATH")
        self.executable = str(Path(executable).resolve())
        self.command = [self.executable, "-axo", "pid=,ppid=,rss="]

    def _snapshot(self) -> Mapping[int, Tuple[int, int]]:
        environment = os.environ.copy()
        environment["LC_ALL"] = "C"
        try:
            completed = subprocess.run(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                timeout=PS_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SamplingUnavailable(f"could not execute ps: {exc}") from exc

        if completed.returncode != 0:
            detail = completed.stderr.strip() or "no diagnostic"
            raise SamplingUnavailable(
                f"ps exited {completed.returncode}: {detail[:500]}"
            )

        processes: Dict[int, Tuple[int, int]] = {}
        for line_number, line in enumerate(completed.stdout.splitlines(), start=1):
            fields = line.split()
            if len(fields) != 3:
                raise SamplingUnavailable(
                    f"unparseable ps row {line_number}: {line[:200]!r}"
                )
            try:
                pid, parent_pid, rss_kib = (int(field) for field in fields)
            except ValueError as exc:
                raise SamplingUnavailable(
                    f"non-integer ps row {line_number}: {line[:200]!r}"
                ) from exc
            if pid <= 0 or parent_pid < 0 or rss_kib < 0:
                raise SamplingUnavailable(
                    f"invalid ps values on row {line_number}: {line[:200]!r}"
                )
            if pid in processes:
                raise SamplingUnavailable(f"duplicate PID {pid} in ps output")
            processes[pid] = (parent_pid, rss_kib)

        if not processes:
            raise SamplingUnavailable("ps returned an empty process snapshot")
        return processes

    def sample_tree(self, root_pid: int) -> TreeSample:
        processes = self._snapshot()
        if root_pid not in processes:
            raise RootProcessGone(f"PID {root_pid} is absent from the ps snapshot")

        children: Dict[int, List[int]] = {}
        for pid, (parent_pid, _rss_kib) in processes.items():
            children.setdefault(parent_pid, []).append(pid)

        pending = [root_pid]
        descendants = set()
        while pending:
            pid = pending.pop()
            if pid in descendants:
                continue
            descendants.add(pid)
            pending.extend(children.get(pid, ()))

        return TreeSample(
            rss_kib=sum(processes[pid][1] for pid in descendants),
            process_count=len(descendants),
        )

    def preflight(self) -> None:
        """Prove that ``ps`` can see and parse this wrapper before target launch."""

        try:
            self.sample_tree(os.getpid())
        except RootProcessGone as exc:
            raise SamplingUnavailable(
                "ps returned a snapshot that does not contain the wrapper process"
            ) from exc


class SignalForwarder:
    """Forward termination signals to the target's dedicated process group."""

    def __init__(self) -> None:
        self.process: Optional[subprocess.Popen[bytes]] = None
        self.received: List[int] = []
        self.forwarded: List[int] = []
        self._old_handlers: Dict[int, signal.Handlers] = {}

    @staticmethod
    def _handled_signals() -> Sequence[int]:
        names = ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT")
        values = []
        for name in names:
            value = getattr(signal, name, None)
            if value is not None and value not in values:
                values.append(value)
        return values

    def install(self) -> None:
        for signum in self._handled_signals():
            self._old_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, self._handle)

    def restore(self) -> None:
        for signum, old_handler in self._old_handlers.items():
            signal.signal(signum, old_handler)
        self._old_handlers.clear()

    def _send_to_group(self, signum: int) -> None:
        if self.process is None:
            return
        try:
            os.killpg(self.process.pid, signum)
            self.forwarded.append(signum)
        except ProcessLookupError:
            pass

    def _handle(self, signum: int, _frame: object) -> None:
        self.received.append(signum)
        # A second signal is an explicit request to stop an unresponsive tree.
        forwarded_signal = signum if len(self.received) == 1 else signal.SIGKILL
        self._send_to_group(forwarded_signal)

    def attach(self, process: subprocess.Popen[bytes]) -> None:
        self.process = process
        if self.received:
            self._send_to_group(self.received[0])
            if len(self.received) > 1:
                self._send_to_group(signal.SIGKILL)


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
    finally:
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink()
            except FileNotFoundError:
                pass


def _finish_metadata(
    metadata: Dict[str, object],
    *,
    monitor_start_monotonic: float,
    status: str,
    return_code: Optional[int],
    wrapper_exit_code: int,
    error_message: Optional[str],
    forwarder: SignalForwarder,
) -> None:
    metadata.update(
        {
            "monitor_end_time_utc": _utc_now(),
            "monitor_elapsed_seconds": round(
                time.monotonic() - monitor_start_monotonic, 6
            ),
            "status": status,
            "return_code": return_code,
            "wrapper_exit_code": wrapper_exit_code,
            "termination_signal": (
                _signal_name(-return_code)
                if return_code is not None and return_code < 0
                else None
            ),
            "received_signals": [_signal_name(signum) for signum in forwarder.received],
            "forwarded_signals": [
                _signal_name(signum) for signum in forwarder.forwarded
            ],
            "error": error_message,
            "sampling_error": (
                error_message if status == "sampling_unavailable" else None
            ),
        }
    )


def _write_or_report(path: Path, metadata: Mapping[str, object]) -> bool:
    try:
        _atomic_write_json(path, metadata)
    except OSError as exc:
        print(
            f"rss monitor: could not write JSON metadata {path}: {exc}", file=sys.stderr
        )
        return False
    return True


def _stop_after_sampling_failure(process: subprocess.Popen[bytes]) -> None:
    """Bound cleanup when measurement becomes invalid after target launch."""

    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=3.0)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_monitored(
    command: Sequence[str],
    *,
    json_path: Path,
    log_path: Path,
    interval_seconds: float,
    cwd: Path,
) -> int:
    """Run one target and return the wrapper's shell-compatible exit status."""

    monitor_start_monotonic = time.monotonic()
    forwarder = SignalForwarder()
    metadata: Dict[str, object] = {
        "schema_version": 2,
        "status": "initialising",
        "command": list(command),
        "command_display": shlex.join(command),
        "cwd": str(cwd),
        "log_path": str(log_path),
        "monitor_start_time_utc": _utc_now(),
        "monitor_end_time_utc": None,
        "monitor_elapsed_seconds": None,
        "start_time_utc": None,
        "end_time_utc": None,
        "end_time_source": None,
        "observed_end_time_utc": None,
        "wall_clock_drift_seconds": None,
        "elapsed_seconds": None,
        "pid": None,
        "return_code": None,
        "wrapper_exit_code": None,
        "termination_signal": None,
        "sample_interval_seconds": interval_seconds,
        "sample_count": 0,
        "peak_rss_kib": 0,
        "rss_unit": "KiB",
        "process_count_at_peak": 0,
        "max_process_count": 0,
        "max_sample_gap_seconds": 0.0,
        "ps_executable": None,
        "ps_command": None,
        "received_signals": [],
        "forwarded_signals": [],
        "error": None,
        "sampling_error": None,
    }

    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle: BinaryIO = log_path.open("wb")
    except OSError as exc:
        print(f"rss monitor: could not prepare output paths: {exc}", file=sys.stderr)
        return SAMPLING_FAILURE_EXIT

    process: Optional[subprocess.Popen[bytes]] = None
    sampler: Optional[ProcessSampler] = None
    status = "initialising"
    error_message: Optional[str] = None
    return_code: Optional[int] = None
    wrapper_exit_code = SAMPLING_FAILURE_EXIT
    command_start_monotonic: Optional[float] = None

    forwarder.install()
    try:
        try:
            sampler = ProcessSampler()
            metadata["ps_executable"] = sampler.executable
            metadata["ps_command"] = sampler.command
            sampler.preflight()
        except SamplingUnavailable as exc:
            status = "sampling_unavailable"
            error_message = str(exc)
            print(f"rss monitor: {error_message}", file=sys.stderr)
        else:
            if forwarder.received:
                status = "interrupted_before_launch"
                wrapper_exit_code = 128 + forwarder.received[0]
            else:
                candidate_start_time = _utc_now()
                candidate_start_monotonic = time.monotonic()
                try:
                    process = subprocess.Popen(
                        list(command),
                        cwd=str(cwd),
                        stdout=log_handle,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                except FileNotFoundError as exc:
                    status = "launch_failed"
                    wrapper_exit_code = COMMAND_NOT_FOUND_EXIT
                    error_message = f"could not launch command: {exc}"
                    print(f"rss monitor: {error_message}", file=sys.stderr)
                except OSError as exc:
                    status = "launch_failed"
                    wrapper_exit_code = LAUNCH_FAILURE_EXIT
                    error_message = f"could not launch command: {exc}"
                    print(f"rss monitor: {error_message}", file=sys.stderr)
                else:
                    metadata["start_time_utc"] = candidate_start_time
                    command_start_monotonic = candidate_start_monotonic
                    metadata["pid"] = process.pid
                    forwarder.attach(process)
                    peak_rss_kib = 0
                    process_count_at_peak = 0
                    max_process_count = 0
                    sample_count = 0
                    max_sample_gap = 0.0
                    last_sample_started: Optional[float] = None
                    next_sample = time.monotonic()

                    try:
                        while True:
                            sample_started = time.monotonic()
                            if last_sample_started is not None:
                                max_sample_gap = max(
                                    max_sample_gap,
                                    sample_started - last_sample_started,
                                )
                            last_sample_started = sample_started

                            try:
                                sample = sampler.sample_tree(process.pid)
                            except RootProcessGone as exc:
                                if process.poll() is not None:
                                    if sample_count == 0:
                                        raise SamplingUnavailable(
                                            "target exited before an RSS sample could be obtained"
                                        ) from exc
                                    break
                                raise SamplingUnavailable(str(exc)) from exc

                            sample_count += 1
                            max_process_count = max(
                                max_process_count, sample.process_count
                            )
                            if sample.rss_kib > peak_rss_kib:
                                peak_rss_kib = sample.rss_kib
                                process_count_at_peak = sample.process_count

                            if process.poll() is not None:
                                break

                            next_sample += interval_seconds
                            wait_seconds = max(0.0, next_sample - time.monotonic())
                            try:
                                process.wait(timeout=wait_seconds)
                                break
                            except subprocess.TimeoutExpired:
                                pass
                    except SamplingUnavailable as exc:
                        error_message = str(exc)
                        status = "sampling_unavailable"
                        print(f"rss monitor: {error_message}", file=sys.stderr)
                        _stop_after_sampling_failure(process)
                        return_code = process.returncode
                        wrapper_exit_code = SAMPLING_FAILURE_EXIT
                    else:
                        return_code = process.wait()
                        status = "completed"
                        wrapper_exit_code = _normalise_exit_code(return_code)
                        if forwarder.received:
                            wrapper_exit_code = 128 + forwarder.received[0]

                    command_end_monotonic = time.monotonic()
                    observed_end_time = _utc_now()
                    elapsed_seconds = round(
                        command_end_monotonic - command_start_monotonic, 6
                    )
                    derived_end_time, wall_clock_drift = _derive_monotonic_end(
                        str(metadata["start_time_utc"]),
                        elapsed_seconds,
                        observed_end_time,
                    )
                    metadata["end_time_utc"] = derived_end_time
                    metadata["end_time_source"] = "monotonic_elapsed_from_start"
                    metadata["observed_end_time_utc"] = observed_end_time
                    metadata["wall_clock_drift_seconds"] = wall_clock_drift
                    metadata["elapsed_seconds"] = elapsed_seconds

                    metadata.update(
                        {
                            "sample_count": sample_count,
                            "peak_rss_kib": peak_rss_kib,
                            "process_count_at_peak": process_count_at_peak,
                            "max_process_count": max_process_count,
                            "max_sample_gap_seconds": round(max_sample_gap, 6),
                        }
                    )
    finally:
        log_handle.close()

    _finish_metadata(
        metadata,
        monitor_start_monotonic=monitor_start_monotonic,
        status=status,
        return_code=return_code,
        wrapper_exit_code=wrapper_exit_code,
        error_message=error_message,
        forwarder=forwarder,
    )
    metadata_written = _write_or_report(json_path, metadata)
    forwarder.restore()
    return wrapper_exit_code if metadata_written else SAMPLING_FAILURE_EXIT


def _self_test(script_path: Path) -> int:
    worker_code = """
import subprocess
import sys
import time

payload = bytearray(4 * 1024 * 1024)
for offset in range(0, len(payload), 4096):
    payload[offset] = 1

child_code = '''
import time
payload = bytearray(4 * 1024 * 1024)
for offset in range(0, len(payload), 4096):
    payload[offset] = 1
print("rss-self-test: descendant", flush=True)
time.sleep(0.8)
'''
child = subprocess.Popen([sys.executable, "-c", child_code])
print("rss-self-test: stdout", flush=True)
print("rss-self-test: stderr", file=sys.stderr, flush=True)
time.sleep(0.4)
raise SystemExit(child.wait())
""".strip()

    try:
        with tempfile.TemporaryDirectory(prefix="run-with-rss-self-test-") as temp_name:
            temp_dir = Path(temp_name)
            json_path = temp_dir / "success.json"
            log_path = temp_dir / "success.log"
            command = [sys.executable, "-c", worker_code]
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--json",
                    str(json_path),
                    "--log",
                    str(log_path),
                    "--interval",
                    "0.05",
                    "--",
                    *command,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                raise AssertionError(
                    "monitored self-test command failed with "
                    f"exit {completed.returncode}: {completed.stderr.strip()}"
                )

            metadata = json.loads(json_path.read_text(encoding="utf-8"))
            log_text = log_path.read_text(encoding="utf-8")
            expected_markers = (
                "rss-self-test: stdout",
                "rss-self-test: stderr",
                "rss-self-test: descendant",
            )
            checks = {
                "schema version": metadata.get("schema_version") == 2,
                "completed status": metadata.get("status") == "completed",
                "zero return code": metadata.get("return_code") == 0,
                "exact command": metadata.get("command") == command,
                "positive sample count": metadata.get("sample_count", 0) > 0,
                "positive peak RSS": metadata.get("peak_rss_kib", 0) > 0,
                "descendant observed": metadata.get("max_process_count", 0) >= 2,
                "stdout/stderr log": all(
                    marker in log_text for marker in expected_markers
                ),
                "positive elapsed time": metadata.get("elapsed_seconds", 0) > 0,
                "monotonic end source": (
                    metadata.get("end_time_source") == "monotonic_elapsed_from_start"
                ),
                "finite wall-clock drift": isinstance(
                    metadata.get("wall_clock_drift_seconds"), (int, float)
                ),
            }
            parsed_timestamps = {}
            for timestamp_field in (
                "start_time_utc",
                "end_time_utc",
                "observed_end_time_utc",
            ):
                value = metadata.get(timestamp_field)
                try:
                    parsed_timestamps[timestamp_field] = datetime.fromisoformat(
                        str(value).replace("Z", "+00:00")
                    )
                except ValueError:
                    checks[f"valid {timestamp_field}"] = False
                else:
                    checks[f"valid {timestamp_field}"] = True
            if {"start_time_utc", "end_time_utc"} <= parsed_timestamps.keys():
                timestamp_elapsed = (
                    parsed_timestamps["end_time_utc"]
                    - parsed_timestamps["start_time_utc"]
                ).total_seconds()
                checks["timestamp interval matches monotonic elapsed"] = abs(
                    timestamp_elapsed - float(metadata["elapsed_seconds"])
                ) < 0.01

            synthetic_end, synthetic_drift = _derive_monotonic_end(
                "2026-01-01T00:00:00.000Z",
                5.0,
                "2026-01-01T00:01:45.000Z",
            )
            checks["clock-jump derivation"] = (
                synthetic_end == "2026-01-01T00:00:05.000Z"
                and synthetic_drift == 100.0
            )
            failed_checks = [name for name, passed in checks.items() if not passed]
            if failed_checks:
                raise AssertionError("failed checks: " + ", ".join(failed_checks))

            signal_json = temp_dir / "signal.json"
            signal_log = temp_dir / "signal.log"
            signal_worker_code = """
import signal
import time

def stop(_signum, _frame):
    print("rss-self-test: target received SIGTERM", flush=True)
    raise SystemExit(42)

signal.signal(signal.SIGTERM, stop)
print("rss-self-test: target ready", flush=True)
while True:
    time.sleep(0.05)
""".strip()
            signalled = subprocess.Popen(
                [
                    sys.executable,
                    str(script_path),
                    "--json",
                    str(signal_json),
                    "--log",
                    str(signal_log),
                    "--interval",
                    "0.05",
                    "--",
                    sys.executable,
                    "-c",
                    signal_worker_code,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            ready_deadline = time.monotonic() + 3.0
            while time.monotonic() < ready_deadline:
                if signalled.poll() is not None:
                    break
                if signal_log.exists() and "rss-self-test: target ready" in signal_log.read_text(
                    encoding="utf-8"
                ):
                    signalled.send_signal(signal.SIGTERM)
                    break
                time.sleep(0.01)
            else:
                signalled.kill()
                signalled.wait()
                raise AssertionError("signal-test target did not become ready")

            try:
                signal_stdout, signal_stderr = signalled.communicate(timeout=3.0)
            except subprocess.TimeoutExpired as exc:
                signalled.kill()
                signal_stdout, signal_stderr = signalled.communicate()
                diagnostic = (signal_stdout + signal_stderr).strip()
                raise AssertionError(
                    "signal-test wrapper did not exit"
                    + (f" ({diagnostic})" if diagnostic else "")
                ) from exc
            signal_metadata = json.loads(signal_json.read_text(encoding="utf-8"))
            signal_log_text = signal_log.read_text(encoding="utf-8")
            signal_checks = {
                "signal wrapper exit": signalled.returncode == 128 + signal.SIGTERM,
                "signal target return": signal_metadata.get("return_code") == 42,
                "signal metadata exit": (
                    signal_metadata.get("wrapper_exit_code") == 128 + signal.SIGTERM
                ),
                "signal recorded": signal_metadata.get("received_signals")
                == ["SIGTERM"],
                "signal forwarded": signal_metadata.get("forwarded_signals")
                == ["SIGTERM"],
                "signal reached target": (
                    "rss-self-test: target received SIGTERM" in signal_log_text
                ),
            }
            failed_checks = [
                name for name, passed in signal_checks.items() if not passed
            ]
            if failed_checks:
                diagnostic = (signal_stdout + signal_stderr).strip()
                raise AssertionError(
                    "failed signal checks: "
                    + ", ".join(failed_checks)
                    + (f" ({diagnostic})" if diagnostic else "")
                )

            unavailable_json = temp_dir / "unavailable.json"
            unavailable_log = temp_dir / "unavailable.log"
            forbidden_sentinel = temp_dir / "command-was-launched"
            unavailable_environment = os.environ.copy()
            unavailable_environment["PATH"] = ""
            unavailable = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--json",
                    str(unavailable_json),
                    "--log",
                    str(unavailable_log),
                    "--",
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; "
                        f"Path({str(forbidden_sentinel)!r}).write_text('launched')"
                    ),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=unavailable_environment,
                check=False,
            )
            unavailable_metadata = json.loads(
                unavailable_json.read_text(encoding="utf-8")
            )
            fail_closed_checks = {
                "sampling failure exit": (
                    unavailable.returncode == SAMPLING_FAILURE_EXIT
                ),
                "sampling failure status": (
                    unavailable_metadata.get("status") == "sampling_unavailable"
                ),
                "target not launched": not forbidden_sentinel.exists(),
                "null target return": unavailable_metadata.get("return_code") is None,
                "empty command log": (
                    unavailable_log.exists() and unavailable_log.stat().st_size == 0
                ),
            }
            failed_checks = [
                name for name, passed in fail_closed_checks.items() if not passed
            ]
            if failed_checks:
                raise AssertionError(
                    "failed fail-closed checks: " + ", ".join(failed_checks)
                )
    except (AssertionError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"run_with_rss self-test: FAIL: {exc}", file=sys.stderr)
        return 1

    print("run_with_rss self-test: PASS")
    return 0


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", dest="json_path", help="output JSON metadata path")
    parser.add_argument(
        "--log", dest="log_path", help="combined stdout/stderr log path"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help=(
            "RSS sampling interval in seconds, greater than 0 and no more than "
            f"{MAX_INTERVAL_SECONDS:g} (default: {DEFAULT_INTERVAL_SECONDS:g})"
        ),
    )
    parser.add_argument(
        "--cwd", help="target working directory (default: current directory)"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run deterministic offline end-to-end checks",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="command after --")
    args = parser.parse_args(argv)

    if args.self_test:
        if args.command or args.json_path or args.log_path or args.cwd:
            parser.error("--self-test cannot be combined with command/output options")
        return args

    if not args.json_path or not args.log_path:
        parser.error("--json and --log are required")
    if not (0.0 < args.interval <= MAX_INTERVAL_SECONDS):
        parser.error(
            f"--interval must be greater than 0 and no more than {MAX_INTERVAL_SECONDS:g}"
        )
    command = list(args.command)
    if command and command[0] == "--":
        command.pop(0)
    if not command:
        parser.error("a command is required after --")
    args.command = command
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    script_path = Path(__file__).resolve()
    if args.self_test:
        return _self_test(script_path)

    json_path = Path(args.json_path).expanduser().resolve()
    log_path = Path(args.log_path).expanduser().resolve()
    if json_path == log_path:
        print(
            "rss monitor: --json and --log must name different files", file=sys.stderr
        )
        return 2
    cwd = Path(args.cwd).expanduser().resolve() if args.cwd else Path.cwd().resolve()
    if not cwd.is_dir():
        print(
            f"rss monitor: target working directory does not exist: {cwd}",
            file=sys.stderr,
        )
        return 2

    return run_monitored(
        args.command,
        json_path=json_path,
        log_path=log_path,
        interval_seconds=args.interval,
        cwd=cwd,
    )


if __name__ == "__main__":
    raise SystemExit(main())

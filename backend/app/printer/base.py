"""Common interface for delivering a print job to a Bambu Lab printer.

Both the LAN and Cloud transports follow the same two-step pattern used by
Bambu's own tools:

  1. Upload the sliced ``.gcode.3mf`` to storage the printer can read.
  2. Publish an MQTT ``project_file`` / ``start_print`` command so the printer
     fetches that file and begins printing.

See docs/ARCHITECTURE.md for the protocol references.
"""
from __future__ import annotations

import abc
from pathlib import Path


class PrinterError(RuntimeError):
    """Raised when uploading to or commanding the printer fails."""


class PrinterClient(abc.ABC):
    """Transport-agnostic client for starting a print from a local file."""

    @abc.abstractmethod
    def upload(self, local_path: Path, remote_name: str) -> str:
        """Upload ``local_path`` and return the remote path/name to print."""

    @abc.abstractmethod
    def start_print(self, remote_name: str, *, job_name: str) -> None:
        """Command the printer to start printing the already-uploaded file."""

    def print_file(self, local_path: Path, *, job_name: str) -> str:
        """Convenience: upload then start. Returns the remote name used."""
        remote_name = Path(local_path).name
        self.upload(local_path, remote_name)
        self.start_print(remote_name, job_name=job_name)
        return remote_name

    def close(self) -> None:  # pragma: no cover - optional cleanup hook
        """Release connections, if any."""

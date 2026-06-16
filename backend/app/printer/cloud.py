"""Bambu Cloud delivery — the "no PC, works anywhere, visible in Handy" path.

This is the project's end goal and also its riskiest piece: Bambu Lab exposes
**no official API**. The flow below mirrors what community projects (pybambu,
bambulabs_api, Bambuddy) reverse-engineered:

  1. POST credentials to the Bambu Cloud auth endpoint -> access token
     (accounts with 2FA also require a verification-code exchange).
  2. Request a cloud storage upload slot, PUT the ``.gcode.3mf`` to it.
  3. Publish a ``start_print`` command to the **cloud** MQTT broker
     (``<region>.mqtt.bambulab.com:8883``), user ``u_<uid>``, password = token,
     topic ``device/<serial>/request``.

It is intentionally implemented as a thin, clearly-marked stub. Before relying
on it we should wrap a maintained library rather than hand-roll the protocol:
    pip install bambulabs-api   # then adapt below

DO NOT trust this against a real account/printer until it has been validated.
See docs/ROADMAP.md Phase 2.
"""
from __future__ import annotations

from pathlib import Path

from .base import PrinterClient, PrinterError

CLOUD_API_BASE = "https://api.bambulab.com"


def _mqtt_host(region: str) -> str:
    region = (region or "us").lower()
    # 'us' uses us.mqtt..., China uses cn.mqtt...
    return f"{region}.mqtt.bambulab.com"


class CloudPrinterClient(PrinterClient):
    def __init__(self, serial: str, token: str, user_id: str, region: str = "us"):
        if not (serial and token and user_id):
            raise PrinterError("Cloud printing requires serial, token, and user_id.")
        self.serial = serial
        self.token = token
        self.user_id = user_id
        self.region = region

    @classmethod
    def login(cls, email: str, password: str, region: str = "us") -> "CloudPrinterClient":
        """Authenticate to Bambu Cloud and return a ready client.

        Not implemented yet — this is the seam where we either call the
        reverse-engineered auth endpoint or delegate to a community library.
        """
        raise PrinterError(
            "Bambu Cloud login is not implemented yet (Phase 2). "
            "Wrap a maintained library such as 'bambulabs-api' here, then "
            "construct CloudPrinterClient with the resulting token + user_id."
        )

    def upload(self, local_path: Path, remote_name: str) -> str:
        raise PrinterError(
            "Bambu Cloud upload is not implemented yet (Phase 2). It must "
            "request a cloud upload slot and PUT the .gcode.3mf to it."
        )

    def start_print(self, remote_name: str, *, job_name: str) -> None:
        raise PrinterError(
            "Bambu Cloud start_print is not implemented yet (Phase 2). It must "
            f"publish to device/{self.serial}/request on {_mqtt_host(self.region)}:8883."
        )

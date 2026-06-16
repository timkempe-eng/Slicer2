"""LAN delivery: FTPS upload + MQTT start-print, no internet required.

Protocol (community-documented, used by Bambu Studio's "send to printer"):
  * FTPS, implicit TLS, port 990, username ``bblp``, password = the printer's
    LAN **Access Code**. Files go to the root (or ``/cache``).
  * MQTT over TLS on port 8883, same access code, topic
    ``device/<serial>/request``. A ``print.project_file`` command tells the
    printer to print an uploaded ``.gcode.3mf``.

This is wired against the documented shape of the protocol but has **not** yet
been validated against a physical A1. Treat as Phase 1 work-in-progress.
"""
from __future__ import annotations

import ftplib
import json
import ssl
import time
from pathlib import Path

from .base import PrinterClient, PrinterError

MQTT_PORT = 8883
FTPS_PORT = 990
FTP_USER = "bblp"


class _ImplicitTLS_FTP(ftplib.FTP_TLS):
    """ftplib speaks explicit FTPS; Bambu printers use *implicit* TLS."""

    def __init__(self, *args, **kwargs):
        self._sock = None
        super().__init__(*args, **kwargs)

    @property
    def sock(self):
        return self._sock

    @sock.setter
    def sock(self, value):
        if value is not None and not isinstance(value, ssl.SSLSocket):
            value = self.context.wrap_socket(value, server_hostname=self.host)
        self._sock = value


class LanPrinterClient(PrinterClient):
    def __init__(self, host: str, serial: str, access_code: str):
        if not (host and serial and access_code):
            raise PrinterError("LAN printing requires host, serial, and access_code.")
        self.host = host
        self.serial = serial
        self.access_code = access_code

    # -- upload -----------------------------------------------------------
    def upload(self, local_path: Path, remote_name: str) -> str:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # printers use a self-signed cert
        ftp = _ImplicitTLS_FTP(context=ctx)
        try:
            ftp.connect(self.host, FTPS_PORT, timeout=30)
            ftp.login(FTP_USER, self.access_code)
            ftp.prot_p()
            with open(local_path, "rb") as fh:
                ftp.storbinary(f"STOR {remote_name}", fh)
        except (ftplib.all_errors, OSError) as exc:  # type: ignore[misc]
            raise PrinterError(f"FTPS upload failed: {exc}") from exc
        finally:
            try:
                ftp.quit()
            except Exception:  # pragma: no cover
                pass
        return remote_name

    # -- start ------------------------------------------------------------
    def start_print(self, remote_name: str, *, job_name: str) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:  # pragma: no cover
            raise PrinterError("paho-mqtt is required for LAN printing.") from exc

        payload = {
            "print": {
                "sequence_id": str(int(time.time())),
                "command": "project_file",
                "param": "Metadata/plate_1.gcode",
                "project_id": "0",
                "profile_id": "0",
                "task_id": "0",
                "subtask_id": "0",
                "subtask_name": job_name,
                "url": f"ftp://{remote_name}",
                "timelapse": False,
                "bed_leveling": True,
                "flow_cali": False,
                "vibration_cali": True,
                "layer_inspect": True,
                "use_ams": False,
            }
        }

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        client = mqtt.Client()
        client.username_pw_set(FTP_USER, self.access_code)
        client.tls_set_context(ctx)

        topic = f"device/{self.serial}/request"
        try:
            client.connect(self.host, MQTT_PORT, keepalive=60)
            client.loop_start()
            info = client.publish(topic, json.dumps(payload), qos=1)
            info.wait_for_publish(timeout=10)
        except Exception as exc:  # noqa: BLE001
            raise PrinterError(f"MQTT start_print failed: {exc}") from exc
        finally:
            client.loop_stop()
            client.disconnect()

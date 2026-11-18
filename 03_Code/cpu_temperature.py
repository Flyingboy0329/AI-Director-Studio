"""In-process, CPU-only LibreHardwareMonitor provider (Windows/netfx)."""
import ctypes
import math
from pathlib import Path
import sys
import time


def package_value(value):
    try:
        value = float(value)
        return value if math.isfinite(value) and 0 < value <= 150 else None
    except (ValueError, TypeError, OverflowError):
        return None


def sensor_directory():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return root / "third_party" / "cpu-sensor" if not getattr(sys, "frozen", False) else root / "hardware_monitor"


class DllCpuPackage:
    """Single-worker ownership: open, update and close on the same thread."""
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else sensor_directory()
        self.computer = None

    def open(self):
        if self.computer is not None:
            return
        from pythonnet import load
        load("netfx")
        import clr
        directory = str(self.directory.resolve())
        if directory not in sys.path:
            sys.path.insert(0, directory)
        clr.AddReference(str(self.directory.resolve() / "LibreHardwareMonitorLib.dll"))
        from LibreHardwareMonitor.Hardware import Computer
        self.computer = Computer()
        self.computer.IsCpuEnabled = True
        try:
            self.computer.Open()
        except BaseException:
            self.close()
            raise

    def read(self):
        if self.computer is None:
            raise RuntimeError("CPU Computer is closed")
        values = []
        for hardware in self.computer.Hardware:
            if str(hardware.HardwareType) != "Cpu":
                continue
            hardware.Update()
            for sensor in hardware.Sensors:
                if (str(sensor.SensorType) == "Temperature"
                        and str(sensor.Name) == "CPU Package"):
                    value = package_value(sensor.Value)
                    if value is not None:
                        values.append(value)
        return values[0] if len(values) == 1 else None

    def close(self):
        computer, self.computer = self.computer, None
        if computer is not None:
            computer.Close()


class CpuPackageSensor:
    """Lazy DLL initialization; failures are unavailable and retry after 30s."""
    def __init__(self, directory=None):
        self.reader = DllCpuPackage(directory)
        self.retry_at = 0.0
        self.status = "DLL: not initialized"

    def read(self):
        if time.monotonic() < self.retry_at:
            return None
        try:
            if not ctypes.windll.shell32.IsUserAnAdmin():
                raise PermissionError("PawnIO CPU access requires Administrator on this installation")
            self.reader.open()
            value = self.reader.read()
            if value is None:
                raise RuntimeError("CPU Package sensor unavailable")
            self.status = "DLL: LibreHardwareMonitorLib / CPU Package"
            return value
        except Exception as exc:
            self.status = f"DLL: {type(exc).__name__}: {exc}"
            self.retry_at = time.monotonic() + 30.0
            self.close()
            return None

    def close(self):
        try:
            self.reader.close()
        except Exception as exc:
            self.status += f"; close: {type(exc).__name__}: {exc}"


import json
import platform
import re
import urllib.request
import psutil

CPU_PACKAGE_HTTP_URL = "http://127.0.0.1:8085/data.json"

class LocalSensorNoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def parse_lhm_cpu_package(data):
    """Accept one Celsius package sensor under an identified CPU node."""
    if not isinstance(data, dict) or data.get("Text") != "Sensor":
        return None

    def walk(node, cpu=""):
        if not isinstance(node, dict):
            return
        if "HardwareId" in node:
            cpu = node.get("HardwareId") if (str(node.get("HardwareId", "")).startswith(("/intelcpu/", "/amdcpu/"))
                   and node.get("ImageURL") == "images_icon/cpu.png") else ""
        if (cpu and node.get("Text") == "CPU Package"
                and node.get("Type") == "Temperature"
                and str(node.get("SensorId", "")).startswith(cpu + "/temperature/")):
            value = node.get("Value")
            if isinstance(value, str):
                match = re.fullmatch(r"\s*([+-]?\d+(?:\.\d+)?)\s*\N{DEGREE SIGN}C\s*", value)
                if match:
                    temperature = package_value(match.group(1))
                    if temperature is not None:
                        yield temperature
        children = node.get("Children", [])
        if isinstance(children, list):
            for child in children:
                yield from walk(child, cpu)

    values = list(walk(data))
    return values[0] if len(values) == 1 else None


def read_lhm_cpu_package_http():
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), LocalSensorNoRedirect())
    request = urllib.request.Request(CPU_PACKAGE_HTTP_URL, headers={"Cache-Control": "no-cache"})
    with opener.open(request, timeout=0.6) as response:
        if response.geturl() != CPU_PACKAGE_HTTP_URL:
            return None
        body = response.read(2 * 1024 * 1024 + 1)
        if len(body) > 2 * 1024 * 1024:
            return None
        return parse_lhm_cpu_package(json.loads(body))



class CpuTemperature:
    """Worker-owned provider; no stale values after a failed poll."""
    def __init__(self):
        self.dll = CpuPackageSensor() if platform.system() == "Windows" else None
        self.status = "CPU Package: not initialized"

    def read(self):
        if self.dll is not None:
            value = package_value(self.dll.read())
            self.status = self.dll.status
            if value is not None:
                return value
            try:
                value = read_lhm_cpu_package_http()
                if value is not None:
                    self.status = "HTTP: " + CPU_PACKAGE_HTTP_URL + " / CPU Package"
                    return value
                self.status += "; HTTP: no unambiguous CPU Package"
            except Exception as exc:
                self.status += "; HTTP: " + type(exc).__name__
        else:
            try:
                values = [package_value(e.current)
                          for chip, entries in psutil.sensors_temperatures().items()
                          if chip.lower() in ("coretemp", "k10temp")
                          for e in entries if "package" in e.label.lower()]
                values = [v for v in values if v is not None]
                if values:
                    self.status = "psutil: CPU Package"
                    return max(values)
            except Exception:
                pass
            self.status = "CPU Package: unavailable"
        return None

    def close(self):
        if self.dll is not None:
            self.dll.close()


COLORS = ("#10B981", "#FBBF24", "#F97316", "#EF4444")


def temperature_limits(device):
    if device == "cpu":
        return (75, 85, 94)
    if re.search(r"RTX\s*5060\s*Ti", device, re.I):
        return (60, 75, 82)
    if re.search(r"RTX\s*3060(?!\s*Ti)", device, re.I):
        return (65, 78, 84)
    # Generic display policy, not a detected manufacturer thermal limit.
    return (60, 75, 82)


def temperature_color(device, value):
    value = package_value(value)
    return "#8C9BAE" if value is None else COLORS[sum(value > x for x in temperature_limits(device))]

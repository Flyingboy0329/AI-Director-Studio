"""Validate the bundled sensor without installing drivers or requesting UAC."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import sys

from cpu_temperature import sensor_directory


def check_bundle(directory=None):
    directory = Path(directory) if directory else sensor_directory()
    expected = json.loads((directory / "SHA256.json").read_text(encoding="utf-8"))
    errors = []
    for name, digest in expected.items():
        if Path(name).name != name:
            errors.append("Invalid manifest filename")
            continue
        path = directory / name
        if not path.is_file():
            errors.append("Missing: " + name)
        elif hashlib.sha256(path.read_bytes()).hexdigest().lower() != digest.lower():
            errors.append("SHA256 mismatch: " + name)
    if "LibreHardwareMonitorLib.dll" not in expected:
        errors.append("Main sensor DLL is not in the manifest")
    return errors


def probe_clr():
    from pythonnet import load
    load("netfx")
    import clr
    directory = str(sensor_directory().resolve())
    if directory not in sys.path:
        sys.path.insert(0, directory)
    clr.AddReference(str(sensor_directory() / "LibreHardwareMonitorLib.dll"))
    from LibreHardwareMonitor.Hardware import Computer
    computer = Computer()
    computer.IsCpuEnabled = True
    computer.Close()  # No Computer.Open(): this probe never opens hardware.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--read", action="store_true", help="Read only when already administrator")
    args = parser.parse_args()
    result = {"bundle": str(sensor_directory()), "hash_errors": check_bundle()}
    if result["hash_errors"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    if sys.platform != "win32":
        result["clr"] = "Windows-only DLL; use platform provider"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    try:
        probe_clr()
        result["clr"] = "PASS: loaded DLL dependencies and constructed Computer; hardware was not opened"
    except Exception as exc:
        result["clr"] = type(exc).__name__ + ": " + str(exc)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    result["administrator"] = bool(ctypes.windll.shell32.IsUserAnAdmin())
    code = 0
    if args.read:
        if not result["administrator"]:
            result["temperature"] = "SKIPPED: administrator consent is required; no elevation or driver installation was attempted"
            code = 2
        else:
            from cpu_temperature import CpuTemperature
            provider = CpuTemperature()
            try:
                result["temperature_c"] = provider.read()
                result["status"] = provider.status
                if result["temperature_c"] is None:
                    code = 2
            finally:
                provider.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    from python_environment import ensure_environment
    ensure_environment()
    raise SystemExit(main())

"""Install an official llama.cpp release matched to OS/backend inside the project."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import json
import zipfile

from path_utils import get_project_root

DEFAULT_TAG = "b12359"  # Reproducible default; --tag selects another official release.


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def choose_assets(assets, tag, system, machine, backend="auto"):
    arch = "arm64" if machine.lower() in ("arm64", "aarch64") else "x64" if machine.lower() in ("amd64", "x86_64") else machine.lower()
    if backend == "auto":
        backend = "metal" if system == "Darwin" else "cuda" if shutil.which("nvidia-smi") else "vulkan"
    if system == "Darwin":
        if backend not in ("metal", "cpu"):
            raise ValueError("macOS 請使用 Metal 套件")
        pattern = f"llama-{tag}-bin-macos-{arch}.tar.gz"
    elif system == "Windows":
        pattern = f"llama-{tag}-bin-win-{'cuda-13.5' if backend == 'cuda' else backend}-{arch}.zip"
    elif system == "Linux":
        suffix = f"cuda-13.5-{arch}" if backend == "cuda" else arch if backend == "cpu" else f"{backend}-{arch}"
        pattern = f"llama-{tag}-bin-ubuntu-{suffix}.tar.gz"
    else:
        raise ValueError("此作業系統請手動安裝 llama-server 並選取引擎")
    selected = [a for a in assets if a["name"] == pattern]
    if not selected:
        raise ValueError(f"官方版本無此套件：{pattern}。請改用 --backend cpu 或手動選取相容引擎。")
    if backend == "cuda":
        runtime_name = (f"cudart-llama-bin-win-cuda-13.5-{arch}.zip" if system == "Windows"
                        else f"cudart-llama-{tag}-bin-ubuntu-cuda-13.5-{arch}.tar.gz")
        runtime = [a for a in assets if a["name"] == runtime_name]
        if not runtime:
            raise ValueError("官方版本缺少對應 CUDA runtime")
        selected += runtime
    return selected, backend


def download_parts(url, path, size):
    chunk = 16 * 1024 * 1024
    parts = [(start, min(size - 1, start + chunk - 1), path.with_name(path.name + f".{start}.part"))
             for start in range(0, size, chunk)]
    def fetch(part):
        start, end, destination = part
        if destination.exists() and destination.stat().st_size == end - start + 1:
            return
        command = ["curl", "-L", "--fail", "--silent", "--show-error", "--retry", "2",
                   "--connect-timeout", "15", "--max-time", "240", "--range", f"{start}-{end}",
                   "-o", str(destination), url + f"?part={start}"]
        subprocess.run(command, check=True)
        if destination.stat().st_size != end - start + 1:
            raise ValueError(f"Incomplete download part: {destination.name}")
        print(f"Downloaded {destination.name}", flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(fetch, parts))
    with path.open("wb") as output:
        for _, _, part in parts:
            with part.open("rb") as stream:
                shutil.copyfileobj(stream, output)


def safe_extract(archive, target):
    target = target.resolve()
    def inside(path):
        resolved = path.resolve()
        if not resolved.is_relative_to(target):
            raise ValueError("Unsafe archive path")
        return resolved
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as package:
            for entry in package.infolist():
                inside(target / entry.filename)
            package.extractall(target)
    else:
        with tarfile.open(archive) as package:
            for entry in package:
                destination = inside(target / entry.name)
                if entry.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                elif entry.isfile():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with package.extractfile(entry) as source, destination.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    destination.chmod(entry.mode & 0o777)
                elif entry.issym():
                    inside(destination.parent / entry.linkname)
                    if not destination.exists():
                        destination.symlink_to(entry.linkname)
                elif entry.islnk():
                    source = inside(target / entry.linkname)
                    if not destination.exists():
                        os.link(source, destination)
                else:
                    raise ValueError("Unsupported archive entry")


def install(tag=DEFAULT_TAG, backend="auto"):
    if not tag or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in tag):
        raise ValueError("Invalid release tag")
    request = urllib.request.Request(f"https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/{tag}", headers={"User-Agent": "AI-Director"})
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    selected, backend = choose_assets(release["assets"], tag, platform.system(), platform.machine(), backend)
    root = get_project_root() / "tools"
    downloads = root / "downloads"
    target = root / f"llama-{tag}-{backend}"
    downloads.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    def fetch(asset):
        name, checksum = asset["name"], asset.get("digest", "")
        if Path(name).name != name or not checksum.startswith("sha256:"):
            raise ValueError("Official asset is missing SHA256 metadata")
        expected = checksum.split(":", 1)[1]
        path = downloads / name
        if not path.exists() or digest(path) != expected:
            url = asset["browser_download_url"]
            if not url.startswith("https://github.com/ggml-org/llama.cpp/releases/download/"):
                raise ValueError("Unexpected download origin")
            if shutil.which("curl"):
                download_parts(url, path, asset["size"])
            else:
                with urllib.request.urlopen(url, timeout=120) as source, path.open("wb") as output:
                    shutil.copyfileobj(source, output)
        if digest(path) != expected:
            raise ValueError(f"SHA256 mismatch: {name}")
        print(f"Verified {name}", flush=True)
        return path
    with ThreadPoolExecutor(max_workers=2) as pool:
        archives = list(pool.map(fetch, selected))
    for archive in archives:
        safe_extract(archive, target)
    print(f"Installed: {target}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=DEFAULT_TAG)
    parser.add_argument("--backend", choices=("auto", "cuda", "vulkan", "cpu", "metal"), default="auto")
    args = parser.parse_args()
    install(args.tag, args.backend)

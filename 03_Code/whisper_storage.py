"""Offline-first project ASR storage; serialize downloads across app processes."""
import hashlib
import json
import shutil
from pathlib import Path

from filelock import FileLock
from faster_whisper.utils import download_model, _MODELS
from path_utils import get_project_root


def model_asset(path):
    return path.name in ('model.bin','config.json','tokenizer.json','preprocessor_config.json') or path.name.startswith('vocabulary.')


def complete_model(directory):
    root = Path(directory)
    try:
        if not (root / 'model.bin').is_file() or (root / 'model.bin').stat().st_size <= 0:
            return False
        for name in ('config.json', 'tokenizer.json'):
            if not isinstance(json.loads((root / name).read_text(encoding='utf-8')), dict):
                return False
        manifest = root / '.ai_director_complete.json'
        if manifest.exists():
            sizes = json.loads(manifest.read_text(encoding='utf-8'))['sizes']
            if any(not (root/name).is_file() or (root/name).stat().st_size != size for name,size in sizes.items()):
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def resolve_whisper_model(selected, notify=print):
    local = Path(selected).expanduser()
    if local.is_dir():
        if not complete_model(local):
            raise ValueError('本機 Whisper 目錄缺少有效 model.bin／config.json／tokenizer.json；不自動替換或下載。')
        notify(f'[Faster-Whisper] 本機完整模型，離線載入：{local.resolve()}')
        return str(local.resolve()), 'local_directory'
    if local.is_absolute() or '\\' in selected or selected.startswith('.'):
        raise FileNotFoundError(f'所選 Whisper 本機目錄不存在：{selected}；不當作網路模型下載。')
    repo = _MODELS.get(selected, selected)
    name = next((alias for alias in ('tiny','base','small','medium','large-v3','turbo')
                 if _MODELS.get(alias) == repo), None)
    name = name or ('model-' + hashlib.sha256(repo.encode()).hexdigest()[:16])
    base = get_project_root() / '04_Models' / 'Whisper'
    base.mkdir(parents=True, exist_ok=True)
    destination = base / name
    # OS-backed file lock is released even on a crash; recheck after acquiring.
    notify(f'[Faster-Whisper] 檢查專案模型：{destination}')
    with FileLock(str(base / (name + '.lock')), timeout=300):
        if complete_model(destination):
            notify('[Faster-Whisper] 專案模型完整，直接離線使用；不連線、不重複下載。')
            return str(destination), 'project_local'
        cached = None
        try:
            candidate = download_model(selected, local_files_only=True)
            if complete_model(candidate):
                cached = Path(candidate)
        except (OSError, ValueError):
            pass
        if cached is not None:
            notify('[Faster-Whisper] 使用既有完整快取複製至專案；不下載。')
            destination.mkdir(parents=True, exist_ok=True)
            for item in cached.iterdir():
                if item.is_file() and model_asset(item):
                    shutil.copy2(item, destination / item.name)
            source = 'cache_import'
        else:
            notify('[Faster-Whisper] 本機尚無完整模型；首次下載／續傳缺檔至專案，保留已有檔案。')
            download_model(selected, output_dir=str(destination))
            source = 'project_download'
        # Verify core files without trusting an older completion manifest.
        for filename in ('model.bin','config.json','tokenizer.json'):
            path = destination / filename
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f'Whisper 尚未完整取得：{filename}；保留檔案供下次續傳。')
        for filename in ('config.json','tokenizer.json'):
            if not isinstance(json.loads((destination/filename).read_text(encoding='utf-8')), dict):
                raise RuntimeError('Whisper 設定或 tokenizer 格式無效，未標記下載完成。')
        sizes = {p.name:p.stat().st_size for p in destination.iterdir()
                 if p.is_file() and model_asset(p)}
        temporary = destination / '.ai_director_complete.tmp'
        temporary.write_text(json.dumps({'repo':repo,'sizes':sizes}), encoding='utf-8')
        temporary.replace(destination / '.ai_director_complete.json')
        return str(destination), source

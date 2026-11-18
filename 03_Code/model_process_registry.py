"""Recover only recorded AI Director llama processes, never arbitrary listeners."""
import json
from pathlib import Path
import subprocess
import uuid
import psutil


class RecoveredProcess:
    def __init__(self, record):
        self.record = record
        self.pid = record['pid']

    def checked(self):
        process = psutil.Process(self.pid)
        if (abs(process.create_time()-self.record['created']) > .01
                or Path(process.exe()).resolve() != Path(self.record['exe']).resolve()
                or process.cmdline() != self.record['command']):
            raise RuntimeError('模型 PID 身分已改變，不會操作此程序')
        return process

    def poll(self):
        try:
            return None if self.checked().is_running() else 0
        except psutil.NoSuchProcess:
            return 0

    def terminate(self):self.checked().terminate()
    def kill(self):self.checked().kill()

    def wait(self, timeout=None):
        try:
            return self.checked().wait(timeout=timeout)
        except psutil.NoSuchProcess:
            return 0
        except psutil.TimeoutExpired as exc:
            raise subprocess.TimeoutExpired('recovered llama-server',timeout) from exc


class ModelProcessRegistry:
    def __init__(self, path):self.path=Path(path)

    def read(self):
        if not self.path.exists():return {}
        data=json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data,dict) or data.get('owner')!='AI_Director' or not isinstance(data.get('servers'),dict):
            raise ValueError('模型程序紀錄格式無效')
        return data['servers']

    def write(self, servers):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps({'owner':'AI_Director','servers':servers},ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(self.path)

    def add(self, role, process, log_path, signature):
        if type(getattr(process,'pid',None)) is not int:
            return None  # Non-process test doubles are never persisted.
        live=psutil.Process(process.pid)
        exe=str(Path(live.exe()).resolve())
        if Path(exe).name.lower() not in ('llama-server','llama-server.exe'):
            raise ValueError('只記錄本程式啟動的 llama-server')
        record={'pid':process.pid,'created':live.create_time(),'exe':exe,'command':live.cmdline(),
                'role':role,'log_path':str(log_path),'signature':list(signature)}
        servers=self.read();key=uuid.uuid4().hex;servers[key]=record;self.write(servers)
        return key

    def remove(self, key):
        if key:
            servers=self.read();servers.pop(key,None);self.write(servers)

    def recover(self, notify):
        servers=self.read();found={}
        for key,record in list(servers.items()):
            try:
                if record.get('role') not in ('llm','vlm') or Path(record['exe']).name.lower() not in ('llama-server','llama-server.exe'):
                    raise ValueError('紀錄不是模型引擎')
                handle=RecoveredProcess(record)
                if handle.poll() is not None:
                    servers.pop(key);continue
                role=record['role']
                if role in found:raise ValueError('相同角色有多個紀錄，請核對')
                found[role]=(handle,Path(record['log_path']),tuple(record['signature']),key)
                command=record['command']
                model=Path(command[command.index('-m')+1]).name if '-m' in command else '模型'
                notify(f"[模型恢復] 已核對本程式 {role.upper()} {model} 背景引擎 PID {record['pid']}；可由『卸除模型』結束。")
            except psutil.NoSuchProcess:
                servers.pop(key)
            except (psutil.Error,OSError,AttributeError,ValueError,KeyError,TypeError,RuntimeError) as exc:
                notify(f"[模型恢復] 無法接管紀錄 {key}：{exc}；不會終止未核對的程序。")
        if servers!=self.read():self.write(servers)
        return found

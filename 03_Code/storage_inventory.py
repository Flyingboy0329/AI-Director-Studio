"""Readable mounted volumes, shared by storage cards and the information view."""
import os
import psutil


def storage_inventory():
    result, seen = [], set()
    try:
        partitions = psutil.disk_partitions()
    except (OSError, psutil.Error):
        return []
    for partition in partitions:
        mount = partition.mountpoint
        key = os.path.normcase(os.path.normpath(mount))
        if key in seen or not partition.fstype or "cdrom" in partition.opts.lower():
            continue
        seen.add(key)
        try:
            usage = psutil.disk_usage(mount)
        except (OSError, psutil.Error):
            continue
        if usage.total <= 0:
            continue
        result.append({"mount": mount, "device": partition.device, "filesystem": partition.fstype,
                       "total_gb": usage.total/1024**3, "free_gb": usage.free/1024**3,
                       "percent": usage.percent})
    return result


def storage_text(disks):
    if not disks:
        return "目前未偵測到可讀取的已掛載磁碟。\n\n未掛載、未插入或無存取權限的磁碟無法顯示容量。"
    blocks = [f"偵測到 {len(disks)} 個可讀取的掛載磁碟／磁碟區。\n容量單位為 GiB（1024³ bytes），以系統掛載資訊為準。"]
    for disk in disks:
        blocks.append(f"{disk['mount']}\n"
                      f"裝置：{disk.get('device') or '未提供'}\n"
                      f"檔案系統：{disk.get('filesystem') or '未提供'}\n"
                      f"總容量：{disk['total_gb']:.1f} GiB\n"
                      f"剩餘：{disk['free_gb']:.1f} GiB　已使用：{disk['percent']:.1f}%")
    blocks.append("資料會隨硬體監控更新，包含系統可辨識且可讀取的內接／外接掛載磁碟；不推測實體硬碟數或連接類型。")
    return "\n\n".join(blocks)

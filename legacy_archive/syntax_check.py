#!/usr/bin/env python3
"""
syntax_check.py
快速語法檢驗腳本 (執行於專案根目錄)
"""
import py_compile
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve()
errors = []
success_count = 0

print("🔍 開始 AI_Director 語法檢驗...\n" + "="*50)

for py_file in sorted(ROOT_DIR.rglob("*.py")):
    # 排除本腳本
    if py_file.name == "syntax_check.py":
        continue
    try:
        py_compile.compile(str(py_file), doraise=True)
        print(f"✅ {py_file.relative_to(ROOT_DIR):<40} [PASS]")
        success_count += 1
    except py_compile.PyCompileError as e:
        print(f"❌ {py_file.relative_to(ROOT_DIR):<40} [FAIL] {e}")
        errors.append((py_file, e))

print("\n" + "="*50)
print(f"📊 檢驗報告：共檢查 {success_count + len(errors)} 個檔案")
if errors:
    print(f"🔴 失敗: {len(errors)} 個")
    for f, e in errors: print(f"   - {f}: {e}")
else:
    print("🟢 全部通過！無語法錯誤。")
    sys.exit(0)

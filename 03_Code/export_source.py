"""Create a clean source archive without local preferences, footage, weights or Git history."""
from pathlib import Path
import zipfile

from path_utils import get_project_root


def export_source():
    root = get_project_root()
    output = root / "05_Output" / "review" / "AI_Director_source.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    allowed = ["README.md", "RELEASE_NOTES.md", "requirements.txt", "requirements-cpu-sensor.txt", ".gitignore", "AI_Director.spec", "Start_AI_Director.cmd", "AI Director Studio.exe", "Build_Windows_Launcher.ps1", "啟動說明.md", "四大主題提示詞.txt", "開始使用.md", "Install_Dependencies.cmd", "Check_CPU_Temperature.cmd", ".gitattributes"]
    files = [root / name for name in allowed]
    private_manifests = {"docs/ORIGINAL_SOURCE_HASHES.json", "docs/RELEASE_FILES_SHA256.txt"}
    for folder in ("03_Code", "resolve_lua", "01_Project/prompts", "docs"):
        files += [p for p in (root / folder).rglob("*") if p.is_file() and
                  not set(p.parts).intersection({"__pycache__", "05_Output", "02_Data", "01_Input"}) and
                  p.relative_to(root).as_posix() not in private_manifests and
                  (p.suffix in (".py", ".lua", ".md", ".cs") or
                   (folder == "docs" and p.suffix in (".svg", ".json", ".csv", ".txt")))]
    files += list((root / "01_Project/prompts").glob("*.txt"))
    files += [root / "01_Project" / name for name in ("app_icon.png", "app_icon.ico", "model_settings.json", "user_config.json")]
    files += [p for p in (root / "third_party").rglob("*") if p.is_file()]
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())
        archive.writestr("02_Data/.gitkeep", "")
        archive.writestr("04_Models/.gitkeep", "")
    print(output)
    return output


if __name__ == "__main__":
    export_source()

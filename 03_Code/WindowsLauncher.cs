// Windowed bootstrapper; application/models remain beside this executable.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;

internal static class WindowsLauncher
{
    private static readonly object LogLock = new object();
    private const string Modules = "('torch','cv2','faster_whisper','PyQt6','psutil','pyautogui','pyperclip','filelock','pythonnet','clr_loader')";

    private static string Quote(string value)
    {
        return "\"" + value.Replace("\"", "\\\"") + "\"";
    }

    private static IEnumerable<string> Candidates(string root)
    {
        string requested = Environment.GetEnvironmentVariable("AI_DIRECTOR_PYTHON");
        if (!String.IsNullOrWhiteSpace(requested)) yield return requested;
        yield return Path.Combine(root, ".venv", "Scripts", "python.exe");
        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string installed = Path.Combine(local, "Programs", "Python");
        if (Directory.Exists(installed))
        {
            string[] folders = Directory.GetDirectories(installed, "Python*");
            Array.Sort(folders, StringComparer.OrdinalIgnoreCase);
            Array.Reverse(folders);
            foreach (string folder in folders) yield return Path.Combine(folder, "python.exe");
        }
        foreach (string folder in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(Path.PathSeparator))
        {
            if (String.IsNullOrWhiteSpace(folder)) continue;
            string path;
            try { path = Path.Combine(folder.Trim('"'), "python.exe"); }
            catch (ArgumentException) { continue; }
            yield return path;
        }
    }

    private static string FindPython(string root)
    {
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        string probe = "import sys,importlib.util;sys.exit(0 if sys.version_info >= (3,10) and all(importlib.util.find_spec(x) is not None for x in " + Modules + ") else 1)";
        foreach (string candidate in Candidates(root))
        {
            try
            {
                string full = Path.GetFullPath(candidate);
                if (!seen.Add(full) || !File.Exists(full)) continue;
                var info = new ProcessStartInfo(full, "-c " + Quote(probe));
                info.UseShellExecute = false;
                info.CreateNoWindow = true;
                info.RedirectStandardOutput = true;
                info.RedirectStandardError = true;
                using (Process process = Process.Start(info))
                {
                    // Probe only checks module discovery; no GPU/model imports.
                    process.BeginOutputReadLine();
                    process.BeginErrorReadLine();
                    if (!process.WaitForExit(15000)) { process.Kill(); process.WaitForExit(); continue; }
                    if (process.ExitCode == 0) return full;
                }
            }
            catch (Exception) { /* Try the next existing interpreter. */ }
        }
        return null;
    }

    private static void Append(string path, string line)
    {
        if (line == null) return;
        lock (LogLock)
        {
            try { File.AppendAllText(path, line + Environment.NewLine, Encoding.UTF8); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        string root = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        bool check = args.Length == 1 && args[0] == "--check";
        string log = null;
        try
        {
            string script = Path.Combine(root, "03_Code", "app_gui.py");
            if (!File.Exists(script)) throw new InvalidOperationException("找不到 03_Code/app_gui.py，請保留完整資料夾，不要單獨搬走啟動器。");
            string logDir = Path.Combine(root, "05_Output", "logs");
            Directory.CreateDirectory(logDir);
            log = Path.Combine(logDir, "launcher_" + DateTime.Now.ToString("yyyyMMdd_HHmmss_fff") + "_" + Process.GetCurrentProcess().Id + ".log");
            string python = FindPython(root);
            if (python == null) throw new InvalidOperationException("找不到 Python 3.10+ 且依賴齊備的環境。請依 README 安裝 requirements.txt，或設定 AI_DIRECTOR_PYTHON 指向現有 python.exe。啟動器不會自動下載或安裝套件。");
            Append(log, "AI Director Studio launcher");
            Append(log, "Application root: " + root);
            Append(log, "Python: " + python);
            if (check) { Append(log, "CHECK PASS: required files and Python modules found; GUI was not started."); return 0; }
            string windowedPython = Path.Combine(Path.GetDirectoryName(python), "pythonw.exe");
            string applicationPython = File.Exists(windowedPython) ? windowedPython : python;
            Append(log, "GUI interpreter: " + applicationPython);
            var info = new ProcessStartInfo(applicationPython, "-X utf8 " + Quote(script));
            info.WorkingDirectory = root;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            info.StandardOutputEncoding = Encoding.UTF8;
            info.StandardErrorEncoding = Encoding.UTF8;
            using (Process process = new Process())
            {
                process.StartInfo = info;
                process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e) { Append(log, e.Data); };
                process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e) { Append(log, e.Data); };
                process.Start();
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                process.WaitForExit();
                if (process.ExitCode != 0) throw new InvalidOperationException("程式未正常啟動或執行中退出。錯誤代碼：" + process.ExitCode);
            }
            return 0;
        }
        catch (Exception error)
        {
            try { if (log != null) Append(log, error.ToString()); } catch (Exception) { }
            if (!check) MessageBox.Show(error.Message + (log == null ? "" : "\n\n日誌：" + log), "AI Director Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}

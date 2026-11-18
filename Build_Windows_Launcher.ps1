$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (!(Test-Path -LiteralPath $compiler)) {
    $compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
}
if (!(Test-Path -LiteralPath $compiler)) { throw 'Windows .NET Framework C# compiler not found.' }
$launcherSource = Join-Path $projectRoot '03_Code\WindowsLauncher.cs'
$launcherIcon = Join-Path $projectRoot '01_Project\app_icon.ico'
$launcherOutput = Join-Path $projectRoot 'AI Director Studio.exe'
if (Test-Path -LiteralPath $launcherOutput) {
    $backupRoot = Join-Path $projectRoot '.local\launcher-backups'
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
    Copy-Item -LiteralPath $launcherOutput -Destination (Join-Path $backupRoot ('AI Director Studio_' + [guid]::NewGuid().ToString('N') + '.exe'))
}
& $compiler /nologo /codepage:65001 /target:winexe /optimize+ /reference:System.Windows.Forms.dll "/win32icon:$launcherIcon" "/out:$launcherOutput" $launcherSource
if ($LASTEXITCODE -ne 0) { throw 'Launcher compilation failed.' }
Write-Output $launcherOutput

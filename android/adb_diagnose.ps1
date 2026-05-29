# Install AViz APK (optional), launch, capture crash logcat.
# Usage:
#   .\android\adb_diagnose.ps1
#   .\android\adb_diagnose.ps1 -Apk "C:\path\to\AViz-debug.apk"

param(
    [string]$Apk = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$Adb = if ($env:ADB) { $env:ADB } else { "C:\platform-tools\adb.exe" }
$LogOut = Join-Path $RepoRoot "aviz_logcat.txt"

function Test-AdbDevice {
    $out = & $Adb devices 2>&1 | Out-String
    if ($out -notmatch "`tdevice") {
        Write-Host "ERROR: Phone not ready. Run: adb devices"
        Write-Host "  - Unlock phone, tap Allow USB debugging, check Always allow"
        exit 1
    }
}

Test-AdbDevice
$deviceLine = (& $Adb devices 2>&1 | Select-String 'device$' | Select-Object -First 1).Line.Trim()
Write-Host "Device OK: $deviceLine"

if ($Apk) {
    if (-not (Test-Path $Apk)) { Write-Error "APK not found: $Apk" }
    Write-Host "Installing $Apk ..."
    & $Adb install -r $Apk
}

Write-Host ""
Write-Host "Looking for AViz package ..."
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pkg = @(
    & $Adb shell pm list packages 2>&1 |
        Where-Object { $_ -is [string] -and $_ -match "^package:(.+)$" } |
        ForEach-Object { if ($_ -match "^package:(.+)$") { $Matches[1] } } |
        Where-Object { $_ -match "aviz" }
)
$ErrorActionPreference = $prevEap

if (-not $pkg) {
    foreach ($guess in @("org.aviz.aviz", "org.kivy.aviz", "org.aviz")) {
        $p = & $Adb shell pm path $guess 2>&1 | Out-String
        if ($p -match "package:") { $pkg = @($guess); break }
    }
}

if (-not $pkg) {
    Write-Host ""
    Write-Host "AViz is NOT installed on this phone."
    Write-Host "1. GitHub -> Actions -> Android APK -> latest green run -> aviz-android-apk artifact"
    Write-Host "2. Download AViz-debug.apk to your PC"
    Write-Host "3. Run:  .\android\adb_diagnose.ps1 -Apk `"C:\path\to\AViz-debug.apk`""
    exit 1
}

$pkg = $pkg | Select-Object -First 1
Write-Host "Package: $pkg"

Write-Host ""
Write-Host "Clearing logcat. Launching AViz on the phone in 3s ..."
& $Adb logcat -c
Start-Sleep -Seconds 1
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $Adb shell monkey -p $pkg -c android.intent.category.LAUNCHER 1 2>&1 | Out-Null
$ErrorActionPreference = $prevEap
Start-Sleep -Seconds 6

Write-Host "Saving logcat -> $LogOut"
& $Adb logcat -d -v time 2>&1 |
    Select-String -Pattern "python|Python|aviz|AViz|Qt|qt|Fatal|FATAL|AndroidRuntime|libc|DEBUG|ImportError|ModuleNotFound|Traceback|shiboken|PySide" -CaseSensitive:$false |
    Set-Content -Path $LogOut -Encoding utf8

$lines = (Get-Content $LogOut | Measure-Object -Line).Lines
Write-Host "Saved $lines lines."
Write-Host ""
Get-Content $LogOut -Tail 40

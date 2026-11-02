[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$InstallTools,
    [switch]$InstallBuildTools,
    [switch]$DownloadModel,
    [string]$BlenderVersion = '5.2.3'
)
$ErrorActionPreference = 'Stop'

if (-not ($InstallTools -or $InstallBuildTools -or $DownloadModel)) {
    Write-Host 'No changes requested. Example:'
    Write-Host '.\Install-Prerequisites.ps1 -InstallTools -InstallBuildTools -DownloadModel'
    Write-Host 'Add -WhatIf to preview. Unreal 5.8 must be installed through Epic Games Launcher.'
    exit 0
}
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw 'Install Microsoft App Installer (WinGet), then rerun this script.'
}
function Install-Package([string]$PackageId, [string[]]$Extra = @()) {
    $packageArgs = @('install', '--id', $PackageId, '--exact', '--source', 'winget', '--accept-source-agreements', '--accept-package-agreements') + $Extra
    if ($PSCmdlet.ShouldProcess($PackageId, 'Install official package through WinGet')) {
        & winget @packageArgs
        # WinGet's already-installed/no-upgrade result is not an installation failure.
        if ($LASTEXITCODE -notin @(0, 3010, -1978335189)) {
            throw "Installer failed for $PackageId (exit $LASTEXITCODE). Read the installer output before continuing."
        }
        if ($LASTEXITCODE -eq 3010) { Write-Warning 'Windows reports that a restart is required. This script will not restart the PC.' }
    }
}
if ($InstallTools) {
    Install-Package 'Python.Python.3.11'
    Install-Package 'Microsoft.VisualStudioCode'
    Install-Package 'BlenderFoundation.Blender' @('--version', $BlenderVersion)
    Install-Package 'Ollama.Ollama'
    Install-Package 'EpicGames.EpicGamesLauncher'
}
if ($InstallBuildTools) {
    $components = '--wait --passive --norestart --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.Windows11SDK.26100'
    Install-Package 'Microsoft.VisualStudio.2022.BuildTools' @('--version', '17.14.44', '--override', $components)
}
if ($DownloadModel -and $PSCmdlet.ShouldProcess('qwen2.5-coder:7b', 'Download the local model (several GB)')) {
    $ollamaPath = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    $ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaCommand) { $ollamaPath = $ollamaCommand.Source }
    if (-not (Test-Path -LiteralPath $ollamaPath)) { throw 'Ollama was not found. Install it first.' }
    try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 }
    catch {
        $serviceLogs = Join-Path $env:LOCALAPPDATA 'GameFoundry'
        New-Item -ItemType Directory -Force -Path $serviceLogs | Out-Null
        $previousOllamaHost = $env:OLLAMA_HOST
        try {
            $env:OLLAMA_HOST = '127.0.0.1:11434'
            Start-Process -FilePath $ollamaPath -ArgumentList 'serve' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $serviceLogs 'ollama-serve.log') -RedirectStandardError (Join-Path $serviceLogs 'ollama-serve-error.log')
        } finally { $env:OLLAMA_HOST = $previousOllamaHost }
        $serviceReady = $false
        for ($attempt = 0; $attempt -lt 15; $attempt++) {
            try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2; $serviceReady = $true; break }
            catch { Start-Sleep -Seconds 1 }
        }
        if (-not $serviceReady) { throw 'Ollama did not start. Open Ollama and retry -DownloadModel.' }
    }
    & $ollamaPath pull 'qwen2.5-coder:7b'
    if ($LASTEXITCODE -ne 0) { throw 'Model download failed. Open Ollama and retry -DownloadModel.' }
}
Write-Host 'Next: install Unreal Engine 5.8 in Epic Games Launcher, open a fresh terminal, run setup.cmd, then Start-GameFoundry.cmd.'
Write-Host 'Existing Build Tools installations may need modification in Visual Studio Installer to add missing MSVC/SDK components. Confirm with the C++ test.'

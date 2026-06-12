# Stop stuck containers and start fresh with .env injected
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

Write-Host "=== Topic2Manim Restart ===" -ForegroundColor Cyan

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example — add your API keys, then re-run this script." -ForegroundColor Yellow
}

function Invoke-DockerWithTimeout {
    param(
        [string]$Label,
        [string[]]$Args,
        [int]$TimeoutSec = 45
    )
    Write-Host "$Label..."
    $job = Start-Job -ScriptBlock {
        param($dockerArgs)
        & docker @dockerArgs 2>&1
    } -ArgumentList (,$Args)
    $done = Wait-Job $job -Timeout $TimeoutSec
    if (-not $done) {
        Stop-Job $job -Force | Out-Null
        Remove-Job $job -Force | Out-Null
        return $false
    }
    Receive-Job $job | Out-Host
    Remove-Job $job -Force | Out-Null
    return ($job.State -ne "Failed")
}

function Test-ServerConfig {
    try {
        return Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/config" -TimeoutSec 10
    } catch {
        return $null
    }
}

$before = Test-ServerConfig
if ($before -and -not $before.PSObject.Properties.Name.Contains("env_file_found")) {
    Write-Host "Detected STALE server (old code, missing env_file_found)." -ForegroundColor Yellow
    Write-Host "Your .env keys are correct on disk but the running container never restarted." -ForegroundColor Yellow
}

if (-not (Invoke-DockerWithTimeout -Label "Stopping old containers" -Args @("kill", "topic2manim", "topic2manim2"))) {
    Write-Host ""
    Write-Host "Docker CLI timed out. Docker Desktop is likely stuck." -ForegroundColor Red
    Write-Host "1. Right-click the Docker whale icon in the system tray" -ForegroundColor Yellow
    Write-Host "2. Choose Quit Docker Desktop and wait until it fully exits" -ForegroundColor Yellow
    Write-Host "3. Start Docker Desktop again and wait until it says Running" -ForegroundColor Yellow
    Write-Host "4. Re-run: .\restart.ps1" -ForegroundColor Yellow
    exit 1
}

Invoke-DockerWithTimeout -Label "Removing old containers" -Args @("rm", "-f", "topic2manim", "topic2manim2") | Out-Null

if (-not (Invoke-DockerWithTimeout -Label "Starting container" -Args @("compose", "up", "-d", "--no-build", "--force-recreate"))) {
    Write-Host "docker compose up timed out. Restart Docker Desktop, then run .\restart.ps1 again." -ForegroundColor Red
    exit 1
}

Write-Host "Waiting for server..."
Start-Sleep -Seconds 12

Write-Host "`nChecking /api/config..."
$config = Test-ServerConfig
if (-not $config) {
    Write-Host "Server not responding yet." -ForegroundColor Red
    Write-Host "Try: docker compose logs -f app" -ForegroundColor Yellow
    exit 1
}

$config | ConvertTo-Json -Depth 5
Write-Host ""

$ok = $true
if (-not $config.PSObject.Properties.Name.Contains("env_file_found")) {
    Write-Host "Still running OLD server code. Force-quit Docker Desktop and re-run this script." -ForegroundColor Red
    $ok = $false
} elseif (-not $config.env_file_found) {
    Write-Host ".env file not found inside container (check ./.env mount)." -ForegroundColor Red
    $ok = $false
}

foreach ($provider in @("kimi", "ollama")) {
    if ($config.configured_llm_providers -contains $provider) {
        Write-Host "$provider LLM: ready" -ForegroundColor Green
    }
}

if ($config.configured_tts_providers -contains "elevenlabs") {
    Write-Host "ElevenLabs TTS: ready" -ForegroundColor Green
} else {
    Write-Host "ElevenLabs TTS: NOT configured in running server" -ForegroundColor Red
    $ok = $false
}

Write-Host "`nOpen http://127.0.0.1:5000" -ForegroundColor Cyan
Write-Host "Defaults: LLM=$($config.defaults.llm_provider), TTS=$($config.defaults.tts_provider)"

if (-not $ok) {
    exit 1
}

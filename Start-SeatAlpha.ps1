param(
    [switch]$ForceUpdate,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $projectRoot "logs"
$stdoutLog = Join-Path $logDir "streamlit.log"
$stderrLog = Join-Path $logDir "streamlit-error.log"
$url = "http://127.0.0.1:8501"
$healthUrl = "$url/_stcore/health"

Set-Location -LiteralPath $projectRoot
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

function Test-SeatAlphaHealth {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 1
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

try {
    $condaCommand = Get-Command conda.exe -ErrorAction SilentlyContinue
    if (-not $condaCommand -and $env:CONDA_EXE) {
        $condaPath = $env:CONDA_EXE
    }
    elseif ($condaCommand) {
        $condaPath = $condaCommand.Source
    }
    else {
        throw "Conda not found. Please install Miniconda/Anaconda and reopen the terminal."
    }

    if ($ForceUpdate) {
        Write-Host "[SeatAlpha] Updating exchange data..." -ForegroundColor Cyan
        & $condaPath run --no-capture-output -n seatalpha python -m pipeline.update --force
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Some exchanges failed to update. Details will be shown in the dashboard."
        }
    }

    if (Test-SeatAlphaHealth) {
        Write-Host "[SeatAlpha] Server is already running." -ForegroundColor Green
        if (-not $NoBrowser) { Start-Process $url }
        exit 0
    }

    Write-Host "[SeatAlpha] Starting local server..." -ForegroundColor Cyan
    $arguments = @(
        "run", "--no-capture-output", "-n", "seatalpha",
        "python", "-m", "streamlit", "run", "app.py",
        "--server.address", "127.0.0.1", "--server.port", "8501",
        "--server.headless", "true"
    )
    $server = Start-Process -FilePath $condaPath -ArgumentList $arguments -WorkingDirectory $projectRoot `
        -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -WindowStyle Hidden -PassThru

    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        if (Test-SeatAlphaHealth) {
            $readyMessage = if ($NoBrowser) { "[SeatAlpha] Ready." } else { "[SeatAlpha] Ready. Opening browser..." }
            Write-Host $readyMessage -ForegroundColor Green
            if (-not $NoBrowser) { Start-Process $url }
            exit 0
        }
        if ($server.HasExited) {
            $details = if (Test-Path -LiteralPath $stderrLog) { Get-Content -LiteralPath $stderrLog -Raw } else { "No error log was produced." }
            throw "Server exited before it was ready.`n$details"
        }
        Start-Sleep -Milliseconds 500
    }

    throw "Server did not become ready within 90 seconds. Check: $stderrLog"
}
catch {
    Write-Host "[SeatAlpha] Startup failed:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "Error log: $stderrLog" -ForegroundColor Yellow
    exit 1
}

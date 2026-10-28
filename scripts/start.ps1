<#
.SYNOPSIS
    Inicia la API de SoporteTI-Agent usando el entorno virtual local.
.EXAMPLE
    .\scripts\start.ps1
    .\scripts\start.ps1 -Port 8080
#>

param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    throw "No existe .venv. Ejecuta primero .\scripts\setup.ps1"
}

. .\.venv\Scripts\Activate.ps1
Write-Host "Iniciando Soporte TI: interfaz en http://127.0.0.1:$Port (API docs en /docs)..." -ForegroundColor Cyan
uvicorn app.main:app --host 127.0.0.1 --reload --reload-dir app --port $Port

<#
.SYNOPSIS
    Prepara el entorno local de SoporteTI-Agent en cualquier equipo Windows.
.DESCRIPTION
    Crea el entorno virtual, instala dependencias, genera el .env local
    (si no existe) y ejecuta las pruebas para validar la instalacion.
.EXAMPLE
    .\scripts\setup.ps1
#>

param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Invoke-CheckedCommand {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "El comando '$Executable' fallo con codigo $LASTEXITCODE."
    }
}

Write-Host "== SoporteTI-Agent: configuracion de entorno ==" -ForegroundColor Cyan

# 1. Detectar Python o el lanzador de Python de Windows
$python = Get-Command python -ErrorAction SilentlyContinue
$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
$pythonExecutable = $null
$pythonArguments = @()

if ($python -and $python.Source -notmatch '\\Microsoft\\WindowsApps\\python(?:3)?\.exe$') {
    $pythonExecutable = $python.Source
} elseif ($pythonLauncher) {
    $pythonExecutable = $pythonLauncher.Source
    $pythonArguments = @("-3")
} else {
    throw "No se encontro un interprete de Python. Instala Python 3.11+ y habilita 'python' o 'py' en el PATH."
}
Write-Host "Python detectado: $pythonExecutable" -ForegroundColor DarkGray

$versionArguments = $pythonArguments + @("--version")
$pythonVersionOutput = & $pythonExecutable @versionArguments
if ($LASTEXITCODE -ne 0 -or $pythonVersionOutput -notmatch "Python\s+(\d+)\.(\d+)\.(\d+)") {
    throw "No se pudo determinar la version del interprete de Python."
}
$pythonVersion = [version]::new([int]$Matches[1], [int]$Matches[2], [int]$Matches[3])
if ($pythonVersion -lt [version]"3.11") {
    throw "Se requiere Python 3.11 o superior. Version detectada: $pythonVersion."
}

# 2. Crear entorno virtual si no existe
if (-not (Test-Path ".venv")) {
    Write-Host "Creando entorno virtual (.venv)..." -ForegroundColor Yellow
    Invoke-CheckedCommand -Executable $pythonExecutable -Arguments ($pythonArguments + @("-m", "venv", ".venv"))
} else {
    Write-Host "Entorno virtual (.venv) ya existe, se reutiliza." -ForegroundColor DarkGray
}

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "No se encontro el interprete del entorno virtual en '$venvPython'."
}

# 4. Instalar dependencias
Write-Host "Instalando dependencias desde requirements.txt..." -ForegroundColor Yellow
Invoke-CheckedCommand -Executable $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
Invoke-CheckedCommand -Executable $venvPython -Arguments @("-m", "pip", "install", "-r", "requirements.txt")

# 5. Crear .env local a partir del ejemplo si no existe
if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Se genero .env a partir de .env.example. Revisa y completa los valores." -ForegroundColor Yellow
} else {
    Write-Host ".env ya existe o no hay .env.example, no se sobrescribe." -ForegroundColor DarkGray
}

# 6. Ejecutar pruebas para validar la instalacion
if (-not $SkipTests) {
    Write-Host "Ejecutando pruebas (pytest)..." -ForegroundColor Yellow
    Invoke-CheckedCommand -Executable $venvPython -Arguments @("-m", "pytest", "tests/", "-v")
} else {
    Write-Host "Pruebas omitidas (-SkipTests)." -ForegroundColor DarkGray
}

Write-Host "`n== Entorno listo ==" -ForegroundColor Green
Write-Host "Para iniciar la API ejecuta: .\scripts\start.ps1" -ForegroundColor Green

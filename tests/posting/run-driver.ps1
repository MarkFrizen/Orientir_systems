#Requires -Version 5.1
<#
.SYNOPSIS
    Единая обёртка запуска драйвера ТестПроведения.epf.

.DESCRIPTION
    Собирает командную строку 1cv8.exe ENTERPRISE и передаёт сценарий драйверу
    строкой «<сценарий>|<файл данных>|<файл отчёта>». Путь к платформе и файловая
    база берутся из .v8-project.json (v8path и databases[default].path).

    Перед запуском и после него прибивает процессы 1cv8*: файловая ИБ однопользовательская,
    второй одновременный сеанс — источник «Неспецифицированная ошибка работы с ресурсом».

    Содержимое файла отчёта печатается в stdout и возвращается строкой.

.PARAMETER Scenario
    Имя сценария драйвера, например export-nomenclature или selftest.

.PARAMETER DataFile
    Путь к файлу данных, который сценарий читает или пишет.

.PARAMETER ReportFile
    Путь к файлу отчёта. Драйвер создаёт его заново, поэтому старый удаляется до запуска.

.PARAMETER TimeoutSeconds
    Таймаут ожидания 1cv8.exe, по умолчанию 10 минут.

.OUTPUTS
    System.String — содержимое файла отчёта.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tests\exchange\run-driver.ps1 `
        -Scenario export-nomenclature `
        -DataFile "$env:TEMP\nom.csv" -ReportFile "$env:TEMP\nom.txt"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Scenario,

    [Parameter(Mandatory = $true)]
    [string]$DataFile,

    [Parameter(Mandatory = $true)]
    [string]$ReportFile,

    [int]$TimeoutSeconds = 600
)

$ErrorActionPreference = 'Stop'

# Кириллица в отчёте должна доезжать до вызывающей стороны без перекодировки.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
try { $OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ConfigPath = Join-Path $ProjectRoot '.v8-project.json'
$EpfPath = Join-Path (Join-Path $ProjectRoot 'build') 'ТестПроведения.epf'
$UserName = 'Администратор'

function Get-ProjectSettings {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Не найден файл настроек проекта: $Path"
    }

    $config = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json

    if ([string]::IsNullOrWhiteSpace($config.v8path)) {
        throw "В $Path не задан v8path — путь к каталогу bin платформы 1С."
    }

    $databases = @($config.databases)
    if ($databases.Count -eq 0) {
        throw "В $Path нет ни одной записи в databases."
    }

    $target = $null
    foreach ($candidate in $databases) {
        if ($candidate.id -eq $config.default) {
            $target = $candidate
            break
        }
    }
    if ($null -eq $target) {
        $target = $databases[0]
    }

    if ([string]::IsNullOrWhiteSpace($target.path)) {
        throw "У базы '$($target.id)' в $Path не задан path — поддерживается только файловая ИБ."
    }

    return [pscustomobject]@{
        V8Path       = [string]$config.v8path
        DatabasePath = [string]$target.path
        DatabaseId   = [string]$target.id
    }
}

function Stop-OneCProcesses {
    param([string]$Reason)

    $stale = @(Get-Process -Name '1cv8*' -ErrorAction SilentlyContinue)
    foreach ($process in $stale) {
        Write-Host ("[run-driver] завершаю процесс {0} (pid {1}): {2}" -f $process.ProcessName, $process.Id, $Reason)
        try {
            $process.Kill()
            [void]$process.WaitForExit(5000)
        }
        catch {
            Write-Warning ("не удалось завершить pid {0}: {1}" -f $process.Id, $_.Exception.Message)
        }
    }

    return $stale.Count
}

# --- подготовка -------------------------------------------------------------

$settings = Get-ProjectSettings -Path $ConfigPath

$exePath = Join-Path $settings.V8Path '1cv8.exe'
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "Не найден 1cv8.exe по пути v8path: $exePath"
}
if (-not (Test-Path -LiteralPath $EpfPath)) {
    throw "Не найдена собранная обработка: $EpfPath (соберите её через epf-build)"
}
if (-not (Test-Path -LiteralPath $settings.DatabasePath)) {
    throw "Не найдена информационная база: $($settings.DatabasePath)"
}

$reportDirectory = Split-Path -Parent $ReportFile
if ($reportDirectory -and -not (Test-Path -LiteralPath $reportDirectory)) {
    [void](New-Item -ItemType Directory -Path $reportDirectory -Force)
}
if (Test-Path -LiteralPath $ReportFile) {
    Remove-Item -LiteralPath $ReportFile -Force
}

$null = Stop-OneCProcesses -Reason 'перед запуском драйвера'

# --- запуск -----------------------------------------------------------------

$commandParameter = $Scenario + '|' + $DataFile + '|' + $ReportFile
$argumentLine = 'ENTERPRISE /F "' + $settings.DatabasePath + '" /N"' + $UserName + '"' +
    ' /Execute "' + $EpfPath + '"' +
    ' /C "' + $commandParameter + '"' +
    ' /DisableStartupDialogs'

Write-Host ("[run-driver] база: {0} ({1})" -f $settings.DatabaseId, $settings.DatabasePath)
Write-Host ("[run-driver] команда: 1cv8.exe " + $argumentLine)

$timeoutMs = $TimeoutSeconds * 1000
$exitCode = $null

try {
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $exePath
    $startInfo.Arguments = $argumentLine
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    [void]$process.Start()

    if (-not $process.WaitForExit($timeoutMs)) {
        try { $process.Kill() } catch { }
        throw "1cv8.exe не завершился за $TimeoutSeconds с ($ReportFile не создан)"
    }

    $exitCode = $process.ExitCode
    $process.Dispose()
}
finally {
    $null = Stop-OneCProcesses -Reason 'после запуска драйвера'
}

if (-not (Test-Path -LiteralPath $ReportFile)) {
    throw "Драйвер не создал файл отчёта: $ReportFile (exit=$exitCode)"
}

$report = Get-Content -LiteralPath $ReportFile -Raw -Encoding UTF8
if ($null -eq $report) { $report = '' }
$report = $report.TrimEnd("`r", "`n")

Write-Host ("[run-driver] exit={0}" -f $exitCode)
Write-Output $report

if ($report -match 'ВЕРДИКТ:\s*FAIL') {
    exit 1
}
if ($report -notmatch 'ВЕРДИКТ:\s*PASS') {
    exit 2
}
exit 0

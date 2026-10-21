#Requires -Version 5.1
<#
.SYNOPSIS
    Сквозной набор автотестов обмена CSV<->1С через драйвер ТестОбмена.epf.

.DESCRIPTION
    Прогоняет восемь сценариев драйвера (tests\exchange\run-driver.ps1), читает файл
    отчёта и сверяет с ожиданиями таблицы ниже две вещи:
      * вердикт обработки — первая строка вида «вердикт обработки: X» / «вердикт: X»
        (именно она говорит о состоявшемся обмене: PASS / ЧАСТИЧНО / FAIL);
      * количество записанных единиц — по счётной строке отчёта, своей для каждого вида.

    Перед первым сценарием, между сценариями и после последнего вызывается сценарий
    «cleanup»: файловая ИБ одна, и повторный импорт тех же кодов упал бы на дублях.

    При несовпадении печатается «FAIL <сценарий>: ожидалось X, получен Y» и прогон
    продолжается — так видны все поломки сразу, а не первая. В конце печатается
    «ИТОГО: N/M»; код возврата 0 — все сценарии сошлись, 1 — были расхождения.

    Запуск:
      powershell -ExecutionPolicy Bypass -File tests\exchange\run-exchange-tests.ps1

.NOTES
    Таблица ожиданий (план 2026-10-21-add-csv-data-exchange-tasks-8.1-9.4, задача 36):
      сценарий                          фикстура                     вердикт    единиц
      import-nomenclature-valid         nomenclature-valid.csv       PASS       3
      import-nomenclature-partial       nomenclature-partial.csv     ЧАСТИЧНО   2
      import-nomenclature-bad-types     nomenclature-bad-types.csv   ЧАСТИЧНО   1
      import-nomenclature-missing-ref   nomenclature-missing-ref.csv ЧАСТИЧНО   1
      import-nomenclature-bad-header    bad-header.csv               FAIL       0
      import-orders-valid               (файл готовит сам драйвер)   PASS       2
      import-orders-broken-line         (файл готовит сам драйвер)   FAIL       0
      import-orders-partial             (файл готовит сам драйвер)   ЧАСТИЧНО   1
#>

[CmdletBinding()]
param(
    [int]$TimeoutSeconds = 240
)

$ErrorActionPreference = 'Stop'

# Кириллица из отчётов должна доезжать до консоли без перекодировки.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
try { $OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$DriverPath = Join-Path $PSScriptRoot 'run-driver.ps1'
$FixtureDir = Join-Path $PSScriptRoot 'fixtures'
$WorkDir = Join-Path ([System.IO.Path]::GetTempPath()) 'exchange-tests'

# --- таблица сценариев ------------------------------------------------------
# CounterPattern — регулярное выражение счётной строки отчёта; первая группа —
# число записанных единиц. Для имени «записано: N» это позиции номенклатуры,
# для «документов: N» и «позиций в базе: N» — заказы и контроль «ничего не создано».
#
# GeneratesData = $true означает, что сценарий сам пишет исходный CSV по пути
# DataFile (так устроены все три заказных сценария). Имя фикстуры в таблице
# остаётся справочным: если отдать сценарию путь к файлу в fixtures\, драйвер
# перезапишет закоммиченную фикстуру. Поэтому для таких строк данные уходят
# во временный каталог.
$Scenarios = @(
    [pscustomobject]@{
        Name           = 'import-nomenclature-valid'
        Fixture        = 'nomenclature-valid.csv'
        Verdict        = 'PASS'
        Count          = 3
        CounterPattern = 'записано:\s*(\d+)'
    }
    [pscustomobject]@{
        Name           = 'import-nomenclature-partial'
        Fixture        = 'nomenclature-partial.csv'
        Verdict        = 'ЧАСТИЧНО'
        Count          = 2
        CounterPattern = 'записано:\s*(\d+)'
    }
    [pscustomobject]@{
        Name           = 'import-nomenclature-bad-types'
        Fixture        = 'nomenclature-bad-types.csv'
        Verdict        = 'ЧАСТИЧНО'
        Count          = 1
        CounterPattern = 'записано:\s*(\d+)'
    }
    [pscustomobject]@{
        Name           = 'import-nomenclature-missing-ref'
        Fixture        = 'nomenclature-missing-ref.csv'
        Verdict        = 'ЧАСТИЧНО'
        Count          = 1
        CounterPattern = 'записано:\s*(\d+)'
    }
    [pscustomobject]@{
        # Заголовок битый: импорт не начинается, строки «записано:» в отчёте нет.
        # Что ничего не создано, доказывает «позиций в базе: 0» для кода из файла.
        Name           = 'import-nomenclature-bad-header'
        Fixture        = 'bad-header.csv'
        Verdict        = 'FAIL'
        Count          = 0
        CounterPattern = 'позиций в базе:\s*(\d+)'
    }
    [pscustomobject]@{
        Name           = 'import-orders-valid'
        Fixture        = 'orders-valid.csv'
        GeneratesData  = $true
        Verdict        = 'PASS'
        Count          = 2
        CounterPattern = 'документов:\s*(\d+)'
    }
    [pscustomobject]@{
        # Сценарий делает два прогона (многострочный документ и документ с датой
        # раньше курса); в обоих «загружено документов: 0».
        Name           = 'import-orders-broken-line'
        Fixture        = 'orders-broken-line.csv'
        GeneratesData  = $true
        Verdict        = 'FAIL'
        Count          = 0
        CounterPattern = 'документов:\s*(\d+)'
    }
    [pscustomobject]@{
        # Фикстуры нет: сценарий сам пишет исходный CSV по пути DataFile.
        Name           = 'import-orders-partial'
        Fixture        = $null
        GeneratesData  = $true
        Verdict        = 'ЧАСТИЧНО'
        Count          = 1
        CounterPattern = 'документов:\s*(\d+)'
    }
)

# Вердикт обработки — первая строка отчёта с таким префиксом. Драйвер дописывает
# в конец собственный «ВЕРДИКТ: PASS/FAIL» (итог своих проверок), поэтому брать
# последнее совпадение нельзя: у ожидаемо-частичных сценариев он тоже PASS.
$VerdictPattern = '(?im)^[^\r\n]*?вердикт(?:\s+обработки)?:\s*(PASS|ЧАСТИЧНО|FAIL)'

function New-WorkDirectory {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        [void](New-Item -ItemType Directory -Path $Path -Force)
    }
    return $Path
}

function Invoke-DriverScenario {
    param(
        [string]$Scenario,
        [string]$DataFile,
        [string]$ReportFile
    )

    # Отдельный процесс: run-driver.ps1 завершается через exit, а в общем
    # пространстве имён это оборвало бы весь набор тестов.
    $arguments = @(
        '-NoProfile'
        '-ExecutionPolicy', 'Bypass'
        '-File', ('"' + $DriverPath + '"')
        '-Scenario', $Scenario
        '-DataFile', ('"' + $DataFile + '"')
        '-ReportFile', ('"' + $ReportFile + '"')
        '-TimeoutSeconds', [string]$TimeoutSeconds
    )

    $output = & powershell.exe @arguments 2>&1
    $exitCode = $LASTEXITCODE

    $report = ''
    if (Test-Path -LiteralPath $ReportFile) {
        $report = Get-Content -LiteralPath $ReportFile -Raw -Encoding UTF8
        if ($null -eq $report) { $report = '' }
        $report = $report.TrimEnd("`r", "`n")
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Report   = $report
        Output   = ($output | Out-String)
    }
}

function Get-FirstVerdict {
    param([string]$Report)

    $match = [regex]::Match($Report, $VerdictPattern)
    if (-not $match.Success) { return $null }
    return $match.Groups[1].Value
}

function Get-FirstCounter {
    param(
        [string]$Report,
        [string]$Pattern
    )

    $match = [regex]::Match($Report, $Pattern)
    if (-not $match.Success) { return $null }
    return [int]$match.Groups[1].Value
}

function Invoke-Cleanup {
    param(
        [string]$WorkDir,
        [string]$Stage
    )

    $dataFile = Join-Path $WorkDir 'cleanup.csv'
    $reportFile = Join-Path $WorkDir 'cleanup.txt'

    $result = Invoke-DriverScenario -Scenario 'cleanup' -DataFile $dataFile -ReportFile $reportFile
    $positionLine = [regex]::Match($result.Report, '(?m)^\s*позиций в справочнике:\s*(\d+)\s*->\s*(\d+)')
    $orderLine = [regex]::Match($result.Report, '(?m)^\s*заказов в базе:\s*(\d+)\s*->\s*(\d+)')

    Write-Host ("[cleanup] {0}: код {1}" -f $Stage, $result.ExitCode)
    if ($positionLine.Success) {
        Write-Host ("[cleanup] {0}: номенклатура {1} -> {2}, заказы {3}" -f `
            $Stage, $positionLine.Groups[1].Value, $positionLine.Groups[2].Value, `
            $(if ($orderLine.Success) { $orderLine.Groups[1].Value + ' -> ' + $orderLine.Groups[2].Value } else { '?' }))
    }

    return $result
}

# --- подготовка -------------------------------------------------------------

if (-not (Test-Path -LiteralPath $DriverPath)) {
    throw "Не найден обёртка драйвера: $DriverPath"
}

$WorkDir = New-WorkDirectory -Path $WorkDir

Write-Host ("[exchange-tests] корень проекта: {0}" -f $ProjectRoot)
Write-Host ("[exchange-tests] рабочий каталог отчётов: {0}" -f $WorkDir)
Write-Host ''

$null = Invoke-Cleanup -WorkDir $WorkDir -Stage 'перед прогоном'

$passed = 0
$failed = New-Object System.Collections.Generic.List[string]

foreach ($scenario in $Scenarios) {
    if (-not $scenario.GeneratesData) {
        $dataFile = Join-Path $FixtureDir $scenario.Fixture
        if (-not (Test-Path -LiteralPath $dataFile)) {
            $message = "нет файла фикстуры: $($scenario.Fixture)"
            Write-Host ("FAIL {0}: {1}" -f $scenario.Name, $message)
            $failed.Add($scenario.Name)
            $null = Invoke-Cleanup -WorkDir $WorkDir -Stage ('после ' + $scenario.Name)
            continue
        }
    }
    else {
        # Драйвер сам наполнит файл данными сценария; путь обязательно вне
        # репозитория, иначе он затрёт закоммиченную фикстуру.
        $dataFile = Join-Path $WorkDir ($scenario.Name + '.csv')
        if (Test-Path -LiteralPath $dataFile) {
            Remove-Item -LiteralPath $dataFile -Force
        }
    }

    $reportFile = Join-Path $WorkDir ($scenario.Name + '.txt')
    $result = Invoke-DriverScenario -Scenario $scenario.Name -DataFile $dataFile -ReportFile $reportFile

    $problems = New-Object System.Collections.Generic.List[string]

    if ([string]::IsNullOrWhiteSpace($result.Report)) {
        $problems.Add("файл отчёта пуст или не создан (код $($result.ExitCode))")
    }
    else {
        $actualVerdict = Get-FirstVerdict -Report $result.Report
        if ($null -eq $actualVerdict) {
            $problems.Add("в отчёте нет строки вердикта, ожидался $($scenario.Verdict)")
        }
        elseif ($actualVerdict -ne $scenario.Verdict) {
            $problems.Add(("вердикт: ожидалось {0}, получен {1}" -f $scenario.Verdict, $actualVerdict))
        }

        $actualCount = Get-FirstCounter -Report $result.Report -Pattern $scenario.CounterPattern
        if ($null -eq $actualCount) {
            $problems.Add(("нет счётной строки «{0}», ожидалось {1}" -f $scenario.CounterPattern, $scenario.Count))
        }
        elseif ($actualCount -ne $scenario.Count) {
            $problems.Add(("записано: ожидалось {0}, получен {1}" -f $scenario.Count, $actualCount))
        }
    }

    if ($problems.Count -eq 0) {
        $passed++
        Write-Host ("PASS {0} (код {1})" -f $scenario.Name, $result.ExitCode)
    }
    else {
        $failed.Add($scenario.Name)
        foreach ($problem in $problems) {
            Write-Host ("FAIL {0}: {1}" -f $scenario.Name, $problem)
        }
        Write-Host '--- отчёт ---'
        foreach ($line in ($result.Report -split "`r?`n")) {
            Write-Host ("    " + $line)
        }
        Write-Host '-------------'
    }

    # Без уборки следующий сценарий упадёт на дублях: импорт встретит свои же коды.
    $null = Invoke-Cleanup -WorkDir $WorkDir -Stage ('после ' + $scenario.Name)
    Write-Host ''
}

$finalCleanup = Invoke-Cleanup -WorkDir $WorkDir -Stage 'после прогона'

# Состояние базы после уборки: 21 элемент номенклатуры и 4 заказа.
$stateProblems = New-Object System.Collections.Generic.List[string]
$positionLine = [regex]::Match($finalCleanup.Report, '(?m)^\s*позиций в справочнике:\s*(\d+)\s*->\s*(\d+)')
$orderLine = [regex]::Match($finalCleanup.Report, '(?m)^\s*заказов в базе:\s*(\d+)\s*->\s*(\d+)')

if (-not $positionLine.Success) {
    $stateProblems.Add('в итоговом отчёте уборки нет строки «позиций в справочнике»')
}
elseif ($positionLine.Groups[2].Value -ne '21') {
    $stateProblems.Add(("номенклатуры в базе: ожидалось 21, получено {0}" -f $positionLine.Groups[2].Value))
}

if (-not $orderLine.Success) {
    $stateProblems.Add('в итоговом отчёте уборки нет строки «заказов в базе»')
}
elseif ($orderLine.Groups[2].Value -ne '4') {
    $stateProblems.Add(("заказов в базе: ожидалось 4, получено {0}" -f $orderLine.Groups[2].Value))
}

if ($stateProblems.Count -gt 0) {
    foreach ($problem in $stateProblems) {
        Write-Host ("FAIL состояние базы: {0}" -f $problem)
    }
    $failed.Add('состояние базы после уборки')
}
else {
    Write-Host 'PASS состояние базы после уборки: 4 заказа, 21 элемент номенклатуры'
}

$total = $Scenarios.Count
$passedCount = $passed

Write-Host ''
Write-Host ("ИТОГО: {0}/{1}" -f $passedCount, $total)

if ($failed.Count -gt 0) {
    Write-Host ("провалились: {0}" -f ($failed -join ', '))
    exit 1
}

exit 0

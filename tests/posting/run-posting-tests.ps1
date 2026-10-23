#Requires -Version 5.1
<#
.SYNOPSIS
    Набор автотестов проведения документов через драйвер ТестПроведения.epf.

.DESCRIPTION
    Прогоняет упорядоченный список сценариев драйвера через обёртку
    tests\posting\run-driver.ps1 (один сценарий - один запуск 1cv8.exe) и
    сверяет результат: сценарий пройден, если обёртка вернула код 0, а файл
    отчёта содержит строку «ВЕРДИКТ: PASS».

    Список сценариев: selftest (проверка самой инфраструктуры:
    конфигурация открывается, в метаданных девять документов, у каждого есть
    модуль объекта), task-addressing (общий модуль ЗадачиИсполнителям
    создаёт задачу с адресацией через регистр АдресацияЗадач), задачи
    проведения: post-order, post-confirmation, post-route,
    post-route-correction, post-event, post-tourist-request, post-incident,
    post-claim и post-compensation-act, а также proc-requests (обработка
    ФормированиеЗапросовПоставщикам создаёт заказы по заявкам в работе,
    повторный запуск не даёт дублей), proc-timings (обработка
    ПересчётТайминговМаршрутов пересчитывает тайминги событий и выявляет
    накладки), proc-overdue (обработка ПросроченныеСрокиИSLA выявляет
    просрочки и создаёт задачи без дублей) и proc-summary (обработка
    СводкаСтатусов даёт количества по статусам, совпадающие с ручным
    подсчётом, и не меняет данные), а также query-saldo (СводкаСтатусов
    считает сальдо претензии по движениям ВзаиморасчётыПоПретензиям:
    требование минус удовлетворение, отмена акта возвращает сумму
    требования) и query-kpi (СводкаСтатусов считает KPI сотрудника по
    оборотам KPIОператоров, которые пишет только проведение документа
    подтверждения услуги: количество операций совпадает с числом
    проведённых подтверждений ответственного, время обработки
    неотрицательно, после отмены проведения оборотов не остаётся,
    сотрудник без операций - нули и пометка «нет операций»).
    Новые сценарии проведения добавляются в таблицу $DefaultScenarios ниже.

    При провале печатается «FAIL <сценарий>» и содержимое отчёта, прогон
    продолжается - так видны все поломки сразу. В конце печатается
    «ИТОГО: N/M»; код возврата 0 - все сценарии прошли, 1 - были провалы.

    Прогон изолирован от предыдущих: сервисный сценарий purge-test удаляет из
    базы всё, что оставили сценарии (объекты с маркером «ТЕСТ: » и объекты,
    помеченные на удаление), и вызывается дважды - до списка сценариев и в
    finally после него, в том числе при падении или таймауте. В «ИТОГО: N/M»
    сервисная фаза не входит: она печатается отдельными строками PASS/FAIL
    purge-test, а её провал даёт код возврата 1.

    Перед каждым запуском и после него обёртка прибивает процессы 1cv8*:
    файловая ИБ однопользовательская, лицензия одна.

    Запуск:
      powershell -ExecutionPolicy Bypass -File tests\posting\run-posting-tests.ps1
      powershell -ExecutionPolicy Bypass -File tests\posting\run-posting-tests.ps1 -Scenario selftest,scenario2

.PARAMETER Scenario
    Сценарии драйвера через запятую. По умолчанию - весь список
    $DefaultScenarios.

.PARAMETER TimeoutSeconds
    Таймаут одного запуска 1cv8.exe, передаётся обёртке. По умолчанию 30
    секунд: висящая дольше 1С почти всегда означает модальный диалог, а не
    долгую работу сценария.
#>

[CmdletBinding()]
param(
    [string]$Scenario = '',
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = 'Stop'

# Кириллица из отчётов должна доезжать до консоли без перекодировки.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
try { $OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$DriverPath = Join-Path $PSScriptRoot 'run-driver.ps1'
$WorkDir = Join-Path ([System.IO.Path]::GetTempPath()) 'posting-tests'

# Упорядоченный список сценариев прогона: порядок задан здесь, а не в
# параметре, чтобы полный набор запускался одной командой без аргументов.
$DefaultScenarios = @('selftest', 'task-addressing', 'post-order', 'post-confirmation', 'post-route', 'post-route-correction', 'post-event', 'post-tourist-request', 'post-incident', 'post-claim', 'post-compensation-act', 'proc-requests', 'proc-timings', 'proc-overdue', 'proc-summary', 'query-saldo', 'query-kpi')

# Сервисный сценарий драйвера: уборка объектов, созданных прогонами. Он не
# входит в список проверок и не считается в «ИТОГО: N/M».
$ServiceScenario = 'purge-test'

$ScenarioList = @($Scenario -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
if ($ScenarioList.Count -eq 0) {
    $ScenarioList = $DefaultScenarios
}

function Invoke-DriverScenario {
    param(
        [string]$Name,
        [string]$DataFile,
        [string]$ReportFile
    )

    # Отдельный процесс: run-driver.ps1 завершается через exit, а в общем
    # пространстве имён это оборвало бы весь набор тестов.
    $arguments = @(
        '-NoProfile'
        '-ExecutionPolicy', 'Bypass'
        '-File', ('"' + $DriverPath + '"')
        '-Scenario', $Name
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

# --- подготовка -------------------------------------------------------------

if (-not (Test-Path -LiteralPath $DriverPath)) {
    throw "Не найдена обёртка драйвера: $DriverPath"
}

if (-not (Test-Path -LiteralPath $WorkDir)) {
    [void](New-Item -ItemType Directory -Path $WorkDir -Force)
}

Write-Host ("[posting-tests] корень проекта: {0}" -f $ProjectRoot)
Write-Host ("[posting-tests] рабочий каталог отчётов: {0}" -f $WorkDir)
Write-Host ("[posting-tests] сценарии: {0}" -f ($ScenarioList -join ', '))
Write-Host ''

function Show-FailureDetails {
    param($Result)

    if (-not [string]::IsNullOrWhiteSpace($Result.Report)) {
        Write-Host '--- отчёт ---'
        foreach ($line in ($Result.Report -split "`r?`n")) {
            Write-Host ("    " + $line)
        }
        Write-Host '-------------'
    }
    else {
        Write-Host '--- вывод обёртки ---'
        foreach ($line in ($Result.Output -split "`r?`n")) {
            if (-not [string]::IsNullOrWhiteSpace($line)) { Write-Host ("    " + $line) }
        }
        Write-Host '---------------------'
    }
}

function Invoke-TestScenario {
    param([string]$Name)

    # Файл данных обязателен для обёртки, даже если сценарий его не читает:
    # контракт командной строки драйвера - «<сценарий>|<данные>|<отчёт>».
    $dataFile = Join-Path $WorkDir ($Name + '.csv')
    $reportFile = Join-Path $WorkDir ($Name + '.txt')

    $result = Invoke-DriverScenario -Name $Name -DataFile $dataFile -ReportFile $reportFile
    $verdictPass = $result.Report -match '(?m)^\s*ВЕРДИКТ:\s*PASS\s*$'

    return [pscustomobject]@{
        Name        = $Name
        ExitCode    = $result.ExitCode
        Report      = $result.Report
        Output      = $result.Output
        VerdictPass = $verdictPass
        Passed      = ($result.ExitCode -eq 0 -and $verdictPass)
    }
}

function Invoke-ServicePhase {
    param([string]$Phase)

    # Сервисная фаза не входит в «ИТОГО: N/M»: это уборка, а не проверка
    # поведения конфигурации. Её падение видно отдельной строкой и делает
    # код возврата ненулевым.
    Write-Host ("[posting-tests] {0}: {1} (уборка тестовых объектов)" -f $Phase, $ServiceScenario)

    $result = Invoke-TestScenario -Name $ServiceScenario

    if ($result.Passed) {
        Write-Host ("PASS {0} ({1}, код {2})" -f $ServiceScenario, $Phase, $result.ExitCode)
        foreach ($line in ($result.Report -split "`r?`n")) {
            if ($line -match '^(ОЧИСТКА|ВЕРДИКТ):') { Write-Host ("    " + $line) }
        }
    }
    else {
        $script:serviceFailed = $true
        Write-Host ("FAIL {0} ({1}), код обёртки {2}" -f $ServiceScenario, $Phase, $result.ExitCode)
        Show-FailureDetails -Result $result
    }

    Write-Host ''
}

$passed = 0
$failed = New-Object System.Collections.Generic.List[string]
$serviceFailed = $false

# Перед прогоном база очищается от следов прошлых запусков: иначе проверки
# количества объектов видят накопленный мусор.
Invoke-ServicePhase -Phase 'до прогона'

try {
    foreach ($name in $ScenarioList) {
        $result = Invoke-TestScenario -Name $name

        if ($result.Passed) {
            $passed++
            Write-Host ("PASS {0} (код {1})" -f $name, $result.ExitCode)
        }
        else {
            $failed.Add($name)
            Write-Host ("FAIL {0}: код обёртки {1}, вердикт PASS в отчёте: {2}" -f `
                $name, $result.ExitCode, $(if ($result.VerdictPass) { 'да' } else { 'нет' }))
            Show-FailureDetails -Result $result
        }

        Write-Host ''
    }
}
finally {
    # Уборка выполняется при любом исходе прогона - после падения, таймаута
    # и прерывания, - чтобы база не осталась засорённой.
    Invoke-ServicePhase -Phase 'после прогона'
}

$total = $ScenarioList.Count

Write-Host ("ИТОГО: {0}/{1}" -f $passed, $total)

if ($failed.Count -gt 0) {
    Write-Host ("провалились: {0}" -f ($failed -join ', '))
    exit 1
}

if ($serviceFailed) {
    Write-Host ("{0} не прошёл ни в одной из фаз - в базе могли остаться тестовые объекты" -f $ServiceScenario)
    exit 1
}

exit 0

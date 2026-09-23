# Запуск дымового теста Vanessa "Открытие форм конфигурации" (xddTestRunner).
# Пользователь ИБ должен существовать и иметь снятый флаг "Защита от опасных действий".
$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$v8project = Get-Content (Join-Path $projectRoot '.v8-project.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$db = $v8project.databases | Where-Object { $_.id -eq $v8project.default } | Select-Object -First 1
$exe = Join-Path $v8project.v8path '1cv8.exe'
$base = $db.path
$user = 'Администратор'

$add = Join-Path $projectRoot 'build\vanessa\add-6.9.5'
$xdd = Join-Path $add 'xddTestRunner.epf'
$test = Join-Path $add 'tests\smoke\Тесты_ОткрытиеФормКонфигурации.epf'

$results = Join-Path $projectRoot 'build\vanessa\results'
New-Item -ItemType Directory -Force -Path $results | Out-Null
Remove-Item (Join-Path $results '*') -Recurse -Force -ErrorAction SilentlyContinue

# Путь к настройкам без пробелов (страховка от разбора /C)
$cfg = Join-Path $env:TEMP 'kursovaya-xdd-smoke.json'
Copy-Item (Join-Path $PSScriptRoot 'xdd-smoke.json') $cfg -Force

$report = Join-Path $results 'xunit-report.xml'
$cparam = 'xddConfig ""' + $cfg + '""; xddRun ЗагрузчикФайла ""' + $test + '""; xddReport ГенераторОтчетаJUnitXML ""' + $report + '""; xddShutdown;'
$argsLine = '/F "' + $base + '" /N"' + $user + '" /RunModeManagedApplication /Execute "' + $xdd + '" /C "' + $cparam + '" /TESTMANAGER /DisableStartupDialogs'

Write-Host "Запуск: $exe"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$p = Start-Process -FilePath $exe -ArgumentList $argsLine -PassThru
if (-not $p.WaitForExit(1200000)) {
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    throw 'Таймаут прогона тестов'
}
Write-Host ("Прогон завершён за {0} с, код {1}" -f [int]$sw.Elapsed.TotalSeconds, $p.ExitCode)

$passed = 0; $failed = 0; $failedNames = @()
Get-ChildItem $results -Filter '*-result.xml' | ForEach-Object {
    $t = Get-Content $_.FullName -Raw -Encoding UTF8
    if ($t -match 'status="passed"') { $passed++ }
    else {
        $failed++
        if ($t -match 'name="([^"]+)"') { $failedNames += $Matches[1] }
    }
}
Write-Host ("Итог: passed = {0}, failed = {1}" -f $passed, $failed)
$failedNames | ForEach-Object { Write-Host "  FAIL: $_" }

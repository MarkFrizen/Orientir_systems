# Запуск внешней обработки "ПроверкаДанных" в пакетном режиме 1С:Предприятие.
# Возвращает 0 при вердикте PASS, 1 при FAIL, 2 если вердикт не найден.
# Перед запуском закройте все окна 1С: лицензия на 1 место.
param(
	[switch]$SkipSessionCheck,
	[int]$TimeoutSec = 240
)
$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$v8project = Get-Content (Join-Path $projectRoot '.v8-project.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$db = $v8project.databases | Where-Object { $_.id -eq $v8project.default } | Select-Object -First 1
$exe = Join-Path $v8project.v8path '1cv8.exe'
$epf = Join-Path $projectRoot 'build\ПроверкаДанных.epf'

$log = Join-Path $env:TEMP 'kursovaya-check.log'
Remove-Item $log -Force -ErrorAction SilentlyContinue

if (-not (Test-Path $epf)) { Write-Host "Не найден файл обработки: $epf"; exit 3 }

if (-not $SkipSessionCheck) {
	$procs = Get-Process -Name 1cv8,1cv8c,1cv8s -ErrorAction SilentlyContinue
	if ($procs) { Write-Host 'Есть запущенные процессы 1С - закройте их (лицензия на 1 место).'; exit 3 }
}

$argsLine = '/F "' + $db.path + '" /N"Администратор" /RunModeManagedApplication /Execute "' + $epf + '" /C "' + $log + '" /TESTMANAGER /DisableStartupDialogs'
Write-Host "Запуск: $exe"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$p = Start-Process -FilePath $exe -ArgumentList $argsLine -PassThru
if (-not $p.WaitForExit($TimeoutSec * 1000)) {
	Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
	Write-Host 'Таймаут ожидания обработки'; exit 3
}
Write-Host ("Завершено за {0} с, код {1}" -f [int]$sw.Elapsed.TotalSeconds, $p.ExitCode)

if (-not (Test-Path $log)) {
	Write-Host '!!! Лог не создан'
	exit 2
}

# Размер файловой базы из 1С не прочитать - дописывает обёртка.
$limitMb = 2048
$sizeMb = [math]::Round((Get-Item (Join-Path $db.path '1Cv8.1CD')).Length / 1MB, 1)
$sizeVerdict = if ($sizeMb -le $limitMb) { 'в пределах лимита' } else { 'превышен' }
$sizeLine = ("Размер ИБ: {0} МБ, порог {1} МБ - {2}" -f $sizeMb, $limitMb, $sizeVerdict)

$lines = @(Get-Content $log -Encoding UTF8)
if ($lines.Count -ge 2) {
	$lines = @($lines[0], $sizeLine) + $lines[1..($lines.Count - 1)]
} else {
	$lines = @($lines) + $sizeLine
}
Set-Content -Path $log -Value $lines -Encoding UTF8

Write-Host '--- Лог ---'
Get-Content $log -Encoding UTF8
Write-Host '--- Конец лога ---'

$verdict = Get-Content $log -Encoding UTF8 | Select-String -Pattern 'ВЕРДИКТ:' | Select-Object -Last 1
if (-not $verdict) {
	Write-Host '!!! Вердикт не найден'
	exit 2
}
if ($verdict.Line -match 'FAIL') { exit 1 }
exit 0

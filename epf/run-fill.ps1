# Запуск внешней обработки "ЗаполнениеНСИ" в пакетном режиме 1С:Предприятие.
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
$epf = Join-Path $projectRoot 'build\ЗаполнениеНСИ.epf'

# Лог пишем в путь без пробелов — страховка от разбора параметра /C
$log = Join-Path $env:TEMP 'kursovaya-fill.log'
Remove-Item $log -Force -ErrorAction SilentlyContinue

if (-not $epf -or -not (Test-Path $epf)) { throw "Не найден файл обработки: $epf" }

if (-not $SkipSessionCheck) {
	$procs = Get-Process -Name 1cv8,1cv8c,1cv8s -ErrorAction SilentlyContinue
	if ($procs) { throw 'Есть запущенные процессы 1С - закройте их (лицензия на 1 место).' }
}

$argsLine = '/F "' + $db.path + '" /N"Администратор" /RunModeManagedApplication /Execute "' + $epf + '" /C "' + $log + '" /TESTMANAGER /DisableStartupDialogs'
Write-Host "Запуск: $exe"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$p = Start-Process -FilePath $exe -ArgumentList $argsLine -PassThru
if (-not $p.WaitForExit($TimeoutSec * 1000)) {
	Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
	throw 'Таймаут ожидания обработки'
}
Write-Host ("Завершено за {0} с, код {1}" -f [int]$sw.Elapsed.TotalSeconds, $p.ExitCode)

if (Test-Path $log) {
	Write-Host '--- Лог ---'
	Get-Content $log -Encoding UTF8
	Write-Host '--- Конец лога ---'
}
else {
	Write-Host '!!! Лог не создан'
}

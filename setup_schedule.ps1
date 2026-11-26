# ตั้งเวลารันอัตโนมัติ (Windows Task Scheduler)
#
#   ใช้งาน:
#     powershell -ExecutionPolicy Bypass -File .\setup_schedule.ps1
#     powershell -ExecutionPolicy Bypass -File .\setup_schedule.ps1 -Status
#     powershell -ExecutionPolicy Bypass -File .\setup_schedule.ps1 -Remove
#
param(
    [switch]$Remove,
    [switch]$Status
)

$ErrorActionPreference = 'Stop'
$root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat    = Join-Path $root 'run.bat'
$logDir = Join-Path $root 'logs'
$log    = Join-Path $logDir 'scheduler.log'
$times  = @('06:00', '17:30')

if (-not (Test-Path $bat)) {
    throw "ไม่พบ run.bat ที่ $bat"
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if ($Status) {
    foreach ($t in $times) {
        $name = 'ThaiFuelPrice-' + $t.Replace(':', '')
        $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($task) {
            $info = Get-ScheduledTaskInfo -TaskName $name
            "{0} : {1} | ล่าสุด {2} | ผล {3}" -f $name, $task.State, $info.LastRunTime, $info.LastTaskResult
        } else {
            "{0} : ยังไม่ได้ตั้ง" -f $name
        }
    }
    return
}

foreach ($t in $times) {
    $name = 'ThaiFuelPrice-' + $t.Replace(':', '')

    if ($Remove) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
        "ลบงาน $name แล้ว"
        continue
    }

    $action = New-ScheduledTaskAction `
        -Execute 'cmd.exe' `
        -Argument ('/c ""{0}" >> "{1}" 2>&1"' -f $bat, $log) `
        -WorkingDirectory $root

    $trigger = New-ScheduledTaskTrigger -Daily -At $t

    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

    Register-ScheduledTask `
        -TaskName $name `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description 'สรุปราคาน้ำมันรายวัน (ปตท.OR) + Telegram' `
        -Force | Out-Null

    "ตั้งเวลา $name เวลา $t ทุกวันแล้ว"
}

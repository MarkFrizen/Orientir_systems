param(
    [Parameter(Mandatory=$true)][string]$Login,
    [Parameter(Mandatory=$true)][string]$Params,
    [Parameter(Mandatory=$true)][string]$OutLog,
    [int]$TimeoutSec = 240,
    [string]$V8Name = "1cv8c.exe",
    [string]$ExtraArgs = ""
)

$ErrorActionPreference = "Continue"
$V8   = "C:\Program Files (x86)\1cv8\8.3.27.1786\bin\$V8Name"
$DB   = "D:\Projects\1C_prj\7 семестр\Kursovaya\db\КурсоваяРабота"
$EPF  = "D:\Projects\1C_prj\7 семестр\Kursovaya\build\ПроверкаДоступа.epf"
$ROOT = "D:\Projects\1C_prj\7 семестр\Kursovaya"

# hygiene: kill leftovers
Get-Process 1cv8* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 700

$start = Get-Date
$dumpsBefore = @(Get-ChildItem "$ROOT\Ошибка_*.zip" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)

# Watchdog job: dismiss the CYRILLIC «1С:Предприятие» license OK dialog by posted
# BM_CLICK on OK/ОК/Да buttons + WM_COMMAND IDOK + VK_RETURN (method proven in task-11b probe2).
$ProcBase = [IO.Path]::GetFileNameWithoutExtension($V8)
$job = Start-Job -ArgumentList $ProcBase -ScriptBlock {
    param($ProcBase)
    Add-Type @"
using System;using System.Text;using System.Collections.Generic;using System.Text.RegularExpressions;using System.Runtime.InteropServices;
public class W {
 public delegate bool CB(IntPtr h,IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumWindows(CB cb,IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h,CB cb,IntPtr l);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h,StringBuilder s,int n);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h,StringBuilder s,int n);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr PostMessage(IntPtr h,uint m,IntPtr w,IntPtr l);
 public static List<IntPtr> Dialogs(){
   var r=new List<IntPtr>();
   var re=new Regex("^1[\u0421C]:\u041f\u0440\u0435\u0434\u043f\u0440\u0438\u044f\u0442\u0438\u0435$");
   EnumWindows(delegate(IntPtr h,IntPtr l){
     if(!IsWindowVisible(h)) return true;
     var t=new StringBuilder(512); GetWindowText(h,t,512);
     var c=new StringBuilder(256); GetClassName(h,c,256);
     if(re.IsMatch(t.ToString()) && c.ToString()=="V8NewLocalFrameBaseWnd"){ r.Add(h); }
     return true;},IntPtr.Zero);
   return r;
 }
 public static void Dismiss(IntPtr h){
   EnumChildWindows(h,delegate(IntPtr ch,IntPtr l){
     var cc=new StringBuilder(256); GetClassName(ch,cc,256);
     var ct=new StringBuilder(512); GetWindowText(ch,ct,512);
     if(cc.ToString()=="Button" && IsWindowVisible(ch)){
       var txt=ct.ToString().Trim();
       if(txt=="OK"||txt=="\u041e\u041a"||txt=="\u0414\u0430"||txt=="Yes"){
         PostMessage(ch,0x00F5,IntPtr.Zero,IntPtr.Zero);
       }
     }
     return true;},IntPtr.Zero);
   PostMessage(h,0x0111,(IntPtr)1,IntPtr.Zero);
   PostMessage(h,0x0100,(IntPtr)0x0D,(IntPtr)0x001C0001);
   PostMessage(h,0x0101,(IntPtr)0x0D,(IntPtr)0xC01C0001);
 }
}
"@
    while ($true) {
        $p = Get-Process $ProcBase -ErrorAction SilentlyContinue
        if (-not $p) { break }
        try { foreach ($h in [W]::Dialogs()) { [W]::Dismiss($h) } } catch {}
        Start-Sleep -Milliseconds 700
    }
}

$argLine = "/F `"$DB`" /N `"$Login`" /P `"`" $ExtraArgs /Execute `"$EPF`" /C `"$Params`" /Out `"$OutLog`" /Exit"
Write-Output "CMD: $V8 $argLine"
$proc = Start-Process -FilePath $V8 -ArgumentList $argLine -PassThru
Write-Output "PROC: $($proc.ProcessName) pid=$($proc.Id) start=$($start.ToString('o'))"

$exited = $proc.WaitForExit($TimeoutSec * 1000)
if ($exited) { $exitCode = $proc.ExitCode } else { $exitCode = "TIMEOUT" }

Stop-Job $job -ErrorAction SilentlyContinue
Remove-Job $job -Force -ErrorAction SilentlyContinue
Get-Process 1cv8* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

$elapsed = [int]((Get-Date) - $start).TotalSeconds
$dumpsAfter = @(Get-ChildItem "$ROOT\Ошибка_*.zip" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
$newDumps = @($dumpsAfter | Where-Object { $dumpsBefore -notcontains $_ })
$leftover = @(Get-Process 1cv8* -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)

Write-Output "RESULT: login=$Login exit=$exitCode seconds=$elapsed newDumps=[$($newDumps -join ';')] leftovers=[$($leftover -join ',')]"

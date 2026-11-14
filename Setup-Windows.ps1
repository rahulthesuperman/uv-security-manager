# Per-user Windows installation. Never requires an administrator account.
$ErrorActionPreference = 'Stop'
$pythonVersion = '3.14.3'
$applicationRoot = Join-Path $env:LOCALAPPDATA 'UVSecurityManager'
$applicationCode = Join-Path $applicationRoot 'app'
$runtimeRoot = Join-Path $applicationRoot 'runtime'
$python = Join-Path $runtimeRoot 'python.exe'
$pythonw = Join-Path $runtimeRoot 'pythonw.exe'
$source = $PSScriptRoot

try {
    if (-not [Environment]::Is64BitOperatingSystem) {
        throw 'This setup requires 64-bit Windows 10/11.'
    }
    foreach ($name in @('app.py', 'storage.py')) {
        if (-not (Test-Path (Join-Path $source $name))) {
            throw 'Extract the entire package into one folder before running Setup-Windows.bat.'
        }
    }
    New-Item -ItemType Directory -Path $applicationRoot -Force | Out-Null
    if (-not (Test-Path $python)) {
        Write-Host 'Downloading the official Python desktop runtime. Internet is needed for this step.'
        $installer = Join-Path $env:TEMP ('UV-Python-' + [guid]::NewGuid().ToString() + '.exe')
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-amd64.exe" -OutFile $installer
            $signature = Get-AuthenticodeSignature -FilePath $installer
            if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notlike '*Python Software Foundation*') {
                throw 'The Python installer signature could not be verified. Setup stopped without running it.'
            }
            Write-Host 'Installing a private runtime for this application...'
            $arguments = @('/quiet', 'InstallAllUsers=0', 'Include_launcher=0', 'Include_test=0', 'Include_doc=0', 'Include_pip=0', 'Include_tcltk=1', 'PrependPath=0', 'AssociateFiles=0', 'Shortcuts=0', "TargetDir=`"$runtimeRoot`"")
            $installProcess = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
            if ($installProcess.ExitCode -notin @(0, 3010)) {
                throw "Runtime installation failed (code $($installProcess.ExitCode))."
            }
        } finally {
            if ($installer -and (Test-Path $installer)) {
                Remove-Item -LiteralPath $installer -Force
            }
        }
    }
    & $python -c 'import tkinter, sqlite3; root = tkinter.Tk(); root.withdraw(); root.destroy()'
    if ($LASTEXITCODE -ne 0) {
        throw 'The desktop runtime did not pass its Tkinter / SQLite check.'
    }
    New-Item -ItemType Directory -Path $applicationCode -Force | Out-Null
    foreach ($name in @('app.py', 'storage.py', 'README.md')) {
        $original = Join-Path $source $name
        $destination = Join-Path $applicationCode $name
        if ((Test-Path $original) -and ([IO.Path]::GetFullPath($original) -ne [IO.Path]::GetFullPath($destination))) {
            Copy-Item -LiteralPath $original -Destination $destination -Force
        }
    }
    $shell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    $startMenu = Join-Path ([Environment]::GetFolderPath('Programs')) 'UV Security Manager'
    New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
    foreach ($shortcutPath in @((Join-Path $desktop 'UV Security Manager.lnk'), (Join-Path $startMenu 'UV Security Manager.lnk'))) {
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $pythonw
        $shortcut.Arguments = '"' + (Join-Path $applicationCode 'app.py') + '"'
        $shortcut.WorkingDirectory = $applicationCode
        $shortcut.Description = 'UV Security System - Clients, assets, service and billing'
        $shortcut.Save()
    }
    Write-Host "Installed to $applicationRoot"
    Write-Host 'Your existing database and attachments have been preserved.'
    Start-Process -FilePath $pythonw -ArgumentList ('"' + (Join-Path $applicationCode 'app.py') + '"')
} catch {
    Write-Error $_
    exit 1
}

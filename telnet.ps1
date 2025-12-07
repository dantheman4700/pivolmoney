$logFile = "serial_log.txt"
while (!(Test-NetConnection 127.0.0.1 -Port 7777 -InformationLevel Quiet)) { 
    Write-Host "Waiting for Python script..." 
    Start-Sleep 1 
}
# Once connected, launch telnet with logging enabled
telnet -f $logFile 127.0.0.1 7777
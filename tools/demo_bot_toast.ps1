# Shows one Windows notification on this computer. Windows PowerShell 5.1 only (WinRT).
# Title and text come from the environment (CATOS_TOAST_TITLE, CATOS_TOAST_BODY) so no
# quoting is involved. Nothing leaves this computer. Used by tools/demo_bot_guardian.py.
$ErrorActionPreference = 'Stop'
$title = $env:CATOS_TOAST_TITLE
$body = $env:CATOS_TOAST_BODY
if (-not $title) { Write-Output 'no_title'; exit 2 }
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
# The identity Windows already knows for Windows PowerShell; no registration needed.
$appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
$t = [System.Security.SecurityElement]::Escape($title)
$b = [System.Security.SecurityElement]::Escape($body)
# scenario=reminder keeps the notification on screen until it is dismissed.
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml("<toast scenario=`"reminder`"><visual><binding template=`"ToastGeneric`"><text>$t</text><text>$b</text></binding></visual><actions><action activationType=`"system`" arguments=`"dismiss`" content=`"`"/></actions></toast>")
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
$toast.Tag = 'catos-demo-bot'
$toast.Group = 'catos'
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId)
$setting = $notifier.Setting
if ($setting -ne [Windows.UI.Notifications.NotificationSetting]::Enabled) { Write-Output "setting=$setting"; exit 3 }
$notifier.Show($toast)
Write-Output "shown setting=$setting"
exit 0

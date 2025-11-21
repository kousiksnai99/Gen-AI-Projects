# Prevent any user prompts
$ProgressPreference = 'SilentlyContinue'
$ConfirmPreference = 'None'

# Required for PSGallery
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Install NuGet provider silently
Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force -Scope AllUsers
Import-PackageProvider -Name NuGet -Force

# Trust PSGallery (Prevents prompt)
Set-PSRepository -Name "PSGallery" -InstallationPolicy Trusted

# Install module without prompt
Install-Module -Name Az.ConnectedMachine -Force -AllowClobber

# Now load SCCM Module
$modulePath = "C:\Program Files (x86)\Microsoft Configuration Manager\AdminConsole\bin\ConfigurationManager.psd1"
Import-Module $modulePath -ErrorAction Stop

# Check SCCM site drives
Get-PSDrive -PSProvider CMSite

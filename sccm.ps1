# Run SCCM cmdlets remotely
# Invoke-Command -Session $session -ScriptBlock {
#     Get-CMScript -SiteCode 'CBL'
# }

# Load SCCM PowerShell module

# Install Hybrid Worker Extension Module (if needed)
Install-Module -Name Az.ConnectedMachine -Force

# Path to SCCM Admin Console Module
$modulePath = "C:\Program Files (x86)\Microsoft Configuration Manager\AdminConsole\bin\ConfigurationManager.psd1"

# Import SCCM Module
Import-Module $modulePath -ErrorAction Stop

# Verify SCCM Site Drive
Write-Output (Get-PSDrive -PSProvider CMSite | Select-Object Name, Root)

# Set SCCM Site Drive (example: CBL)
# cd CBL:

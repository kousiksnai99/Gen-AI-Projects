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
Exception calling "ShouldContinue" with "2" argument(s): "A command that prompts the user failed because the host 
program or the command type does not support user interaction. The host was attempting to request confirmation with the 
following message: PowerShellGet requires NuGet provider version '2.8.5.201' or newer to interact with NuGet-based 
repositories. The NuGet provider must be available in 'C:\Program Files\PackageManagement\ProviderAssemblies' or 
'C:\WINDOWS\system32\config\systemprofile\AppData\Local\PackageManagement\ProviderAssemblies'. You can also install the 
NuGet provider by running 'Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force'. Do you want 
PowerShellGet to install and import the NuGet provider now?"
At C:\Program Files (x86)\WindowsPowerShell\Modules\PowerShellGet\1.0.0.1\PSModule.psm1:7455 char:8
+     if($Force -or $psCmdlet.ShouldContinue($shouldContinueQueryMessag ...
+        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (:) [], MethodInvocationException
    + FullyQualifiedErrorId : HostException
 

Install-Module : NuGet provider is required to interact with NuGet-based repositories. Please ensure that '2.8.5.201' 
or newer version of NuGet provider is installed.
At line:9 char:1
+ Install-Module -Name Az.ConnectedMachine -Force
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [Install-Module], InvalidOperationException
    + FullyQualifiedErrorId : CouldNotInstallNuGetProvider,Install-Module

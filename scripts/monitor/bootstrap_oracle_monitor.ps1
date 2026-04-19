param(
    [Parameter(Mandatory = $true)]
    [string]$HostIp,

    [Parameter(Mandatory = $false)]
    [string]$RemoteUser = "opc",

    [Parameter(Mandatory = $false)]
    [string]$SshKeyPath = "$HOME\.ssh\do_agent_ed25519",

    [Parameter(Mandatory = $false)]
    [string]$RemoteRepoDir = "/opt/gpu-skill-builder"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $SshKeyPath)) {
    throw "SSH key not found: $SshKeyPath"
}

Write-Host "Copying monitor installer and env template..."
ssh -i $SshKeyPath -o StrictHostKeyChecking=no "$RemoteUser@$HostIp" "mkdir -p $RemoteRepoDir/scripts/monitor"
scp -i $SshKeyPath -o StrictHostKeyChecking=no `
    "scripts/monitor/install_monitor_service.sh" `
    "scripts/monitor/monitor_env.example" `
    "$RemoteUser@${HostIp}:$RemoteRepoDir/scripts/monitor/"

Write-Host "Ensuring script executable..."
ssh -i $SshKeyPath -o StrictHostKeyChecking=no "$RemoteUser@$HostIp" "chmod +x $RemoteRepoDir/scripts/monitor/install_monitor_service.sh"

Write-Host "Bootstrap uploaded."
Write-Host "Next on remote host:"
Write-Host "  1) Copy $RemoteRepoDir/scripts/monitor/monitor_env.example to $RemoteRepoDir/.env and fill tokens/keys."
Write-Host "  2) Run: sudo bash $RemoteRepoDir/scripts/monitor/install_monitor_service.sh --repo-dir $RemoteRepoDir --env-file $RemoteRepoDir/.env"

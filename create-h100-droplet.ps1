# Create an H100 droplet on DigitalOcean
# Size: gpu-h100x1-80gb (80 GB VRAM) in tor1 (Toronto)
# Image: gpu-h100x1-base (NVIDIA AI/ML Ready)

$token = (doctl auth token 2>$null).Trim()
if (-not $token) {
    Write-Output "CRITICAL: doctl not authenticated. Run: doctl auth init"
    exit 1
}

$headers = @{
    Authorization  = "Bearer $token"
    "Content-Type" = "application/json"
}

Write-Output "=== Creating H100 droplet (gpu-h100x1-80gb, tor1) ==="

$body = @{
    name       = "agent-harness-h100"
    region     = "tor1"
    size       = "gpu-h100x1-80gb"
    image      = "gpu-h100x1-base"
    ssh_keys   = @("55531916")
    project_id = "8513a898-7103-4d2f-a503-ffb24008e609"
    tags       = @("gpu", "h100", "agent-harness", "llm")
} | ConvertTo-Json

try {
    $resp = Invoke-RestMethod -Method Post -Uri "https://api.digitalocean.com/v2/droplets" -Headers $headers -Body $body
    $droplet = $resp.droplet
    Write-Output "Droplet created!"
    Write-Output "  ID:     $($droplet.id)"
    Write-Output "  Name:   $($droplet.name)"
    Write-Output "  Status: $($droplet.status)"
    Write-Output "  Region: $($droplet.region.slug)"
    Write-Output "  Size:   $($droplet.size_slug)"
    Write-Output ""
    Write-Output "Waiting for active status and public IP..."

    $maxWait = 300
    $elapsed = 0
    $interval = 10
    while ($elapsed -lt $maxWait) {
        Start-Sleep -Seconds $interval
        $elapsed += $interval
        $check = Invoke-RestMethod -Uri "https://api.digitalocean.com/v2/droplets/$($droplet.id)" -Headers $headers
        $status = $check.droplet.status
        $publicIP = ($check.droplet.networks.v4 | Where-Object { $_.type -eq "public" }).ip_address

        if ($status -eq "active" -and $publicIP) {
            Write-Output ""
            Write-Output "=== DROPLET ACTIVE ==="
            Write-Output "  ID:     $($check.droplet.id)"
            Write-Output "  IP:     $publicIP"
            Write-Output "  Status: $status"
            Write-Output "  Region: $($check.droplet.region.slug)"
            Write-Output "  Size:   $($check.droplet.size_slug)"
            Write-Output ""
            Write-Output "SSH command:"
            Write-Output "  ssh -i C:\Users\keith\.ssh\do_agent_ed25519 root@$publicIP"
            $publicIP | Out-File -FilePath "C:\Users\keith\dev\gpu-skill-builder\h100-ip.txt" -NoNewline
            exit 0
        }
        Write-Output "  ...${elapsed}s — status=$status, ip=$publicIP"
    }
    Write-Output "TIMEOUT: droplet did not become active within ${maxWait}s"
    exit 1
} catch {
    Write-Output "FAILED to create droplet: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
        Write-Output $reader.ReadToEnd()
        $reader.Close()
    }
    exit 1
}

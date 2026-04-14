$token = (Select-String -Path "C:\Users\keith\dev\.env" -Pattern "^DIGITALOCEAN_ACCESS_TOKEN=" |
    ForEach-Object { $_.Line.Split("=",2)[1] })
$headers = @{
    Authorization  = "Bearer $token"
    "Content-Type" = "application/json"
}

# List available GPU images first
Write-Output "=== Checking available GPU images ==="
$images = Invoke-RestMethod -Uri "https://api.digitalocean.com/v2/images?type=distribution&per_page=200" -Headers $headers
$gpuImages = $images.images | Where-Object { $_.slug -like "gpu-*" }
foreach ($img in $gpuImages) {
    Write-Output "  $($img.slug) - $($img.description)"
}

Write-Output ""
Write-Output "=== Creating H200 droplet ==="

$body = @{
    name       = "agent-harness-h200"
    region     = "nyc2"
    size       = "gpu-h200x1-141gb"
    image      = "gpu-h100x1-base"
    ssh_keys   = @("55531916")
    project_id = "8513a898-7103-4d2f-a503-ffb24008e609"
    tags       = @("gpu", "h200", "agent-harness", "llm")
} | ConvertTo-Json

try {
    $resp = Invoke-RestMethod -Method Post -Uri "https://api.digitalocean.com/v2/droplets" -Headers $headers -Body $body
    $droplet = $resp.droplet
    Write-Output "Droplet created!"
    Write-Output "  ID: $($droplet.id)"
    Write-Output "  Name: $($droplet.name)"
    Write-Output "  Status: $($droplet.status)"
    Write-Output ""
    Write-Output "Waiting for droplet to become active and get an IP..."

    # Poll for active status and IP
    $maxWait = 300
    $elapsed = 0
    $interval = 10
    while ($elapsed -lt $maxWait) {
        Start-Sleep -Seconds $interval
        $elapsed += $interval
        $check = Invoke-RestMethod -Uri "https://api.digitalocean.com/v2/droplets/$($droplet.id)" -Headers $headers
        $status = $check.droplet.status
        $networks = $check.droplet.networks.v4
        $publicIP = ($networks | Where-Object { $_.type -eq "public" }).ip_address

        if ($status -eq "active" -and $publicIP) {
            Write-Output ""
            Write-Output "=== DROPLET IS ACTIVE ==="
            Write-Output "  ID: $($check.droplet.id)"
            Write-Output "  IP: $publicIP"
            Write-Output "  Status: $status"
            Write-Output "  Region: $($check.droplet.region.slug)"
            Write-Output "  Size: $($check.droplet.size_slug)"
            Write-Output ""
            Write-Output "SSH command:"
            Write-Output "  ssh -i C:\Users\keith\.ssh\oci_ampere_ed25519 root@$publicIP"
            # Save IP for next step
            $publicIP | Out-File -FilePath "C:\Users\keith\dev\gpu-skill-builder\h200-ip.txt" -NoNewline
            exit 0
        }
        Write-Output "  ...${elapsed}s - status: $status, IP: $publicIP"
    }
    Write-Output "TIMEOUT waiting for droplet to become active"
    exit 1
} catch {
    Write-Output "FAILED to create droplet:"
    Write-Output $_.Exception.Message
    # Try to get response body
    if ($_.Exception.Response) {
        $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
        Write-Output $reader.ReadToEnd()
        $reader.Close()
    }
    exit 1
}

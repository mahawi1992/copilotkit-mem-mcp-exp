function Search-Brave {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Query,
        [int]$Count = 10
    )

    $body = @{
        query = $Query
        count = $Count
    } | ConvertTo-Json

    $result = Invoke-RestMethod -Method 'Post' -Uri 'http://localhost:8000/search' -ContentType 'application/json' -Body $body
    $result.results | Format-Table title, url -Wrap
}

# Example usage:
# Search-Brave "python programming"
# Search-Brave -Query "javascript frameworks" -Count 5

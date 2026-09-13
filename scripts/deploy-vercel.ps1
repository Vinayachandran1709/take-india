param(
  [ValidateSet("storefront", "dashboard", "all")]
  [string] $Target = "all",
  [string] $ApiUrl = "https://backend-production-b809.up.railway.app/api/v1",
  [switch] $Preview
)

$ErrorActionPreference = "Stop"

function Deploy-VercelApp {
  param(
    [string] $Directory,
    [string] $Project,
    [string] $VariableName
  )

  $targetArgs = @()
  if (-not $Preview) {
    $targetArgs += "--prod"
  }

  npx.cmd -y vercel@latest env add $VariableName production,preview,development `
    --value $ApiUrl --yes --force --no-sensitive --cwd $Directory --project $Project

  npx.cmd -y vercel@latest deploy $Directory --yes --project $Project @targetArgs --logs
}

if ($Target -eq "storefront" -or $Target -eq "all") {
  Deploy-VercelApp -Directory "storefront" -Project "take-india-storefront" -VariableName "NEXT_PUBLIC_API_URL"
}

if ($Target -eq "dashboard" -or $Target -eq "all") {
  Deploy-VercelApp -Directory "dashboard" -Project "take-india-dashboard" -VariableName "VITE_API_URL"
}

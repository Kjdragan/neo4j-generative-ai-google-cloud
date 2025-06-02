#!/bin/pwsh
# Script to delete a GCP Project

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectID
)

Write-Host "DEBUG: Script started. ProjectID parameter value: '$ProjectID'" # For explicit debugging

Write-Host "!!! WARNING !!!" -ForegroundColor Red
Write-Host "You are about to delete the GCP Project with ID: '$ProjectID'" -ForegroundColor Yellow
Write-Host "This action is IRREVERSIBLE and will permanently delete all resources and data within this project." -ForegroundColor Yellow
Write-Host ""

$confirmation = Read-Host "Are you absolutely sure you want to delete project '$ProjectID'? Type 'YES' to confirm, or anything else to cancel:"

if ($confirmation -ne "YES") {
    Write-Host "Project deletion cancelled by user." -ForegroundColor Green
    exit 0
}

Write-Host "Proceeding with deletion of project '$ProjectID'..." -ForegroundColor Cyan

# Attempt to delete the project
gcloud projects delete $ProjectID

if ($LASTEXITCODE -eq 0) {
    Write-Host "Project '$ProjectID' has been scheduled for deletion." -ForegroundColor Green
    Write-Host "It might take some time for the project to be fully purged from the system." -ForegroundColor Green
} else {
    Write-Host "Failed to delete project '$ProjectID'." -ForegroundColor Red
    Write-Host "Please check the error messages above. You might need to resolve dependencies or check permissions." -ForegroundColor Red
    Write-Host "You can also try deleting it manually via the Google Cloud Console." -ForegroundColor Yellow
    exit 1
}

exit 0

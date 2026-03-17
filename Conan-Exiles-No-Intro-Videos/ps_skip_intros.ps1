# Define the path to the ini file storage and keywords
$iniPathFile = "$PSScriptRoot\path.ini"
$keywords = @(
    "bWaitForMoviesToComplete=True",
    "bMoviesAreSkippable=True",
    "+StartupMovies=StartupUE4",
    "+StartupMovies=StartupNvidia",
    "+StartupMovies=CinematicIntroV2"
)
$replacements = @(
    "bWaitForMoviesToComplete=False",
    "bMoviesAreSkippable=True",
    ";+StartupMovies=StartupUE4",
    ";+StartupMovies=StartupNvidia",
    ";+StartupMovies=CinematicIntroV2"
)

# Select the INI file
if (Test-Path $iniPathFile) {
    $iniPath = Get-Content -Path $iniPathFile
} else {
    $iniPath = Read-Host "Enter the path to DefaultGame.ini"
    $iniPath | Out-File $iniPathFile
}

# Modify lines in the ini file
if (Test-Path $iniPath) {
    (Get-Content -Path $iniPath) | ForEach-Object {
        $line = $_
        for ($i = 0; $i -lt $keywords.Length; $i++) {
            if ($line -like "*$($keywords[$i])*") {
                $line = $line -replace $keywords[$i], $replacements[$i]
            }
        }
        $line
    } | Set-Content -Path $iniPath
    Write-Output "Modifications applied successfully."
} else {
    Write-Output "INI file not found."
}

# Launch Conan Exiles
Start-Process "steam://rungameid/440900"

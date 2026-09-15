# Если 7z.exe не в PATH, укажи полный путь:
$sevenZip = "C:\Users\User\scoop\shims\7z.exe"

# Если путь другой — поменяй. Можно узнать, где установлен 7-Zip.

$archives = Get-ChildItem -Filter *.7z
foreach ($archive in $archives) {
    Write-Host "Распаковка $($archive.Name)..."
    # x — извлечь с сохранением структуры, -o — папка назначения (та же), -y — без подтверждений
    & $sevenZip x $archive.FullName -o"$($archive.DirectoryName)" -y
}
Write-Host "Готово. Нажми Enter, чтобы выйти."
Read-Host

все правильно?
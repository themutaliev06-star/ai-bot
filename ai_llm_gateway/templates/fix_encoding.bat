@echo off
chcp 65001 >nul
echo 🔧 Исправляем пути в HTML файлах...

powershell -Command "
$files = Get-ChildItem -Filter '*.html'
foreach ($file in $files) {
    Write-Host 'Обрабатываю:' $file.Name
    $content = Get-Content $file.FullName -Encoding UTF8
    $content = $content -replace 'href=\"static/', 'href=\"/static/'
    $content = $content -replace 'src=\"static/', 'src=\"/static/'
    $content = $content -replace 'href=\"css/', 'href=\"/static/css/'
    $content = $content -replace 'src=\"js/', 'src=\"/static/js/'
    $content | Set-Content $file.FullName -Encoding UTF8
}
"

echo ✅ Пути исправлены!
echo 📁 Теперь проверь: http://127.0.0.1:8800/dashboard_ops
pause
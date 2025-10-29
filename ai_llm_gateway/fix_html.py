import os
import glob

def fix_html_files():
    templates_dir = "templates"
    
    # Находим все HTML файлы
    html_files = glob.glob(os.path.join(templates_dir, "*.html"))
    
    for file_path in html_files:
        print(f"Исправляю {file_path}...")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Исправляем пути к статическим файлам
        content = content.replace('href="static/', 'href="/static/')
        content = content.replace('src="static/', 'src="/static/')
        content = content.replace('href="css/', 'href="/static/css/')
        content = content.replace('src="js/', 'src="/static/js/')
        
        # Добавляем базовую структуру если её нет
        if '</head>' in content and 'style.css' not in content:
            head_insert = '    <link rel="stylesheet" href="/static/css/style.css">\n    <script src="/static/js/app.js"></script>'
            content = content.replace('</head>', head_insert + '\n</head>')
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ {file_path} исправлен")

if __name__ == "__main__":
    fix_html_files()
    print("🎉 Все HTML файлы исправлены!")
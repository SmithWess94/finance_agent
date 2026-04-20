import os
from pathlib import Path
from typing import Dict

def load_knowledge_base() -> str:
    """Загружает все файлы знаний из папки knowledge_base."""
    kb_path = Path('knowledge_base')
    combined_kb = ""
    
    for file in sorted(kb_path.glob('*.md')):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                combined_kb += f"\n### {file.stem}\n{f.read()}\n"
        except Exception as e:
            print(f"Ошибка при загрузке {file}: {e}")
    
    return combined_kb if combined_kb else "(База знаний ещё не заполнена)"

def get_knowledge_base_status() -> Dict[str, bool]:
    """Проверяет, какие файлы знаний загружены."""
    kb_path = Path('knowledge_base')
    required_files = ['kiyosaki.md', 'babylon.md', 'housel.md', 'hill.md', 'schaefer.md']
    
    return {name: (kb_path / name).exists() for name in required_files}

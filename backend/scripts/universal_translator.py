"""
Universal Codebase Translator
Translates Chinese text, comments, docstrings, and strings to English safely and cleanly.
"""
import os
import re
import sys
import py_compile
from pathlib import Path
from typing import List, Dict, Set

# Ensure backend modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.utils.llm_client import LLMClient

client = LLMClient()
chinese_char_pattern = re.compile(r"[\u4e00-\u9fff]")
chinese_phrase_pattern = re.compile(r"[\u4e00-\u9fff][\u4e00-\u9fff\w\s，。！？、（）“”：《》【】\.\-\:\,\?\!\(\)\"\x27]*[\u4e00-\u9fff]|[\u4e00-\u9fff]")

def clean_fullwidth_punct(text: str) -> str:
    replacements = {
        "（": "(", "）": ")", "【": "[", "】": "]",
        "“": "\"", "”": "\"", "‘": "'", "’": "'",
        "：": ": ", "；": "; ", "，": ", ", "。": ". ",
        "！": "! ", "？": "? ", "、": ", "
    }
    for fw, hw in replacements.items():
        text = text.replace(fw, hw)
    return text

def translate_items(items: List[str]) -> Dict[str, str]:
    if not items:
        return {}
    
    mapping = {}
    chunk_size = 25
    for start_idx in range(0, len(items), chunk_size):
        chunk = items[start_idx:start_idx + chunk_size]
        payload = "\n".join([f"---ITEM {i}---\n{item}" for i, item in enumerate(chunk)])
        
        prompt = f"""Translate each numbered item below from Chinese into clear, natural, professional English suitable for production software code, comments, docstrings, and log messages.
CRITICAL RULES:
1. Preserve variable placeholders like {{e}}, {{count}}, {{file}}, {{title}} exactly as they are.
2. Maintain technical software meaning.
3. Keep the exact delimiter format:
---ITEM <id>---
<English translation>

Items to translate:
{payload}
"""
        try:
            res = client.call_with_retry(prompt, "")
            current_id = None
            current_lines = []
            
            for line in res.splitlines():
                line_stripped = line.strip()
                if line_stripped.startswith("---ITEM ") and line_stripped.endswith("---"):
                    if current_id is not None and current_id < len(chunk):
                        trans = "\n".join(current_lines).strip()
                        if trans:
                            mapping[chunk[current_id]] = trans
                    try:
                        current_id = int(line_stripped[8:-3].strip())
                    except ValueError:
                        current_id = None
                    current_lines = []
                elif current_id is not None:
                    current_lines.append(line)
            
            if current_id is not None and current_id < len(chunk):
                trans = "\n".join(current_lines).strip()
                if trans:
                    mapping[chunk[current_id]] = trans
        except Exception as err:
            print(f"Error during chunk translation: {err}")
            
    return mapping

def translate_file(file_path: Path) -> int:
    content = file_path.read_text(encoding="utf-8")
    if not chinese_char_pattern.search(content):
        return 0
    
    # Extract unique phrases and lines with Chinese
    lines = content.splitlines()
    unique_items = set()
    for line in lines:
        if chinese_char_pattern.search(line):
            # If line is comment, extract comment content
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                unique_items.add(stripped.lstrip("#/").strip())
            else:
                matches = chinese_phrase_pattern.findall(line)
                for m in matches:
                    if m.strip():
                        unique_items.add(m.strip())
    
    # Fallback to general matches if none extracted
    if not unique_items:
        matches = set(chinese_phrase_pattern.findall(content))
        unique_items = {m.strip() for m in matches if m.strip()}
    
    sorted_items = sorted(unique_items, key=len, reverse=True)
    translations = translate_items(sorted_items)
    
    new_content = content
    for orig, trans in sorted(translations.items(), key=lambda x: len(x[0]), reverse=True):
        if orig in new_content:
            new_content = new_content.replace(orig, trans)
    
    # Clean lingering fullwidth punctuation
    new_content = clean_fullwidth_punct(new_content)
    
    # Syntax check
    if file_path.suffix == ".py":
        try:
            compile(new_content, str(file_path), "exec")
            file_path.write_text(new_content, encoding="utf-8")
            rem = len(chinese_char_pattern.findall(new_content))
            print(f"SUCCESS: {file_path} -> {rem} Chinese chars remaining")
            return rem
        except Exception as e:
            print(f"SYNTAX ERROR in {file_path}: {e}")
            return len(chinese_char_pattern.findall(content))
    else:
        file_path.write_text(new_content, encoding="utf-8")
        rem = len(chinese_char_pattern.findall(new_content))
        print(f"SUCCESS: {file_path} -> {rem} Chinese chars remaining")
        return rem

if __name__ == "__main__":
    targets = sys.argv[1:]
    if not targets:
        print("Usage: python universal_translator.py <file_or_dir>...")
        sys.exit(1)
    
    for target in targets:
        p = Path(target)
        if p.is_file():
            translate_file(p)
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "venv", "dist", "__pycache__", "build"]]
                for f in files:
                    if f.endswith((".py", ".ts", ".tsx")):
                        translate_file(Path(root) / f)

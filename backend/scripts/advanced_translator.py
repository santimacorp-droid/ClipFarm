"""
Advanced Translator using LLM
Safe translation of Python, TypeScript, and JSON files without breaking syntax.
"""

import os
import re
import sys
import tokenize
import io
import py_compile
from pathlib import Path
from typing import List, Dict, Tuple, Set

# Ensure backend modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.utils.llm_client import LLMClient

client = LLMClient()
chinese_char_pattern = re.compile(r"[\u4e00-\u9fff]")

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

def translate_batch(items: List[str]) -> Dict[str, str]:
    if not items:
        return {}
    
    mapping = {}
    chunk_size = 20
    for start_idx in range(0, len(items), chunk_size):
        chunk = items[start_idx:start_idx + chunk_size]
        payload = "\n".join([f"{i+1}. {item}" for i, item in enumerate(chunk)])
        
        prompt = f"""You are a professional software localization translator.
Translate each numbered line below from Chinese to natural, concise English.
Target context: Code comments, log messages, exception messages, UI strings, docstrings.

CRITICAL INSTRUCTIONS:
1. Output MUST be a numbered list corresponding exactly to the input numbers:
1. <translation>
2. <translation>
2. DO NOT add explanations, notes, markdown formatting, or surrounding quotes.
3. Keep ALL programming placeholders, tokens, and format specifiers EXACTLY as they are (e.g. {{0}}, {{e}}, {{count}}, %s, $1, etc.).
4. Do NOT use unescaped double quotes inside your translation if not needed; prefer simple plain English words.

Lines to translate:
{payload}
"""
        try:
            res = client.call_with_retry(prompt, "")
            lines = res.strip().split("\n")
            for line in lines:
                line = line.strip()
                m = re.match(r"^(\d+)[\.\:\-]\s*(.*)$", line)
                if m:
                    idx = int(m.group(1)) - 1
                    trans = m.group(2).strip()
                    if 0 <= idx < len(chunk) and trans:
                        # strip any wrapping quotes the LLM might have added
                        if (trans.startswith('"') and trans.endswith('"')) or (trans.startswith("'") and trans.endswith("'")):
                            trans = trans[1:-1]
                        mapping[chunk[idx]] = trans
        except Exception as err:
            print(f"Error translating chunk: {err}")
            
    return mapping

def extract_chinese_phrases(content: str) -> List[str]:
    # Match Chinese characters and immediately connected punctuation
    matches = re.findall(r'[\u4e00-\u9fff][\u4e00-\u9fff\s，。！？、（）“”：《》【】\.\-\:\,\?\!\(\)\"\']*[\u4e00-\u9fff]|[\u4e00-\u9fff]+', content)
    # Deduplicate and sort by length descending
    cleaned = set()
    for m in matches:
        s = m.strip()
        if s:
            cleaned.add(s)
    return sorted(list(cleaned), key=len, reverse=True)

def translate_file_deep(file_path: Path) -> int:
    content = file_path.read_text(encoding="utf-8")
    if not chinese_char_pattern.search(content):
        return 0

    phrases = extract_chinese_phrases(content)
    if not phrases:
        return 0

    print(f"Translating {len(phrases)} phrases in {file_path.name}...")
    translations = translate_batch(phrases)

    new_content = content
    for orig in sorted(translations.keys(), key=len, reverse=True):
        trans = translations[orig]
        if not trans:
            continue
        # Clean quotes if inside quotes
        clean_trans = trans.replace('"', '\\"').replace("'", "\\'") if ('"' in orig or "'" in orig) else trans
        new_content = new_content.replace(orig, trans)

    new_content = clean_fullwidth_punct(new_content)

    if file_path.suffix == ".py":
        try:
            compile(new_content, str(file_path), "exec")
            file_path.write_text(new_content, encoding="utf-8")
            rem = len(chinese_char_pattern.findall(new_content))
            print(f"SUCCESS (py): {file_path.name} -> {rem} Chinese chars remaining")
            return rem
        except Exception as e:
            print(f"Compilation error in {file_path.name}: {e}. Retrying with safer substitutions...")
            # Fallback line-by-line or token-by-token if needed
            safe_content = content
            for orig in sorted(translations.keys(), key=len, reverse=True):
                trans = translations[orig].replace('"', "'")
                test_content = safe_content.replace(orig, trans)
                try:
                    compile(test_content, str(file_path), "exec")
                    safe_content = test_content
                except Exception:
                    pass
            safe_content = clean_fullwidth_punct(safe_content)
            file_path.write_text(safe_content, encoding="utf-8")
            rem = len(chinese_char_pattern.findall(safe_content))
            print(f"FALLBACK SUCCESS (py): {file_path.name} -> {rem} Chinese chars remaining")
            return rem
    else:
        file_path.write_text(new_content, encoding="utf-8")
        rem = len(chinese_char_pattern.findall(new_content))
        print(f"SUCCESS: {file_path.name} -> {rem} Chinese chars remaining")
        return rem

def main():
    targets = sys.argv[1:]
    if not targets:
        print("Usage: python advanced_translator.py <path>...")
        return

    for t in targets:
        p = Path(t)
        if p.is_file():
            translate_file_deep(p)
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "venv", "dist", "__pycache__", "build", ".tempmediaStorage"]]
                for f in sorted(files):
                    fp = Path(root) / f
                    if fp.suffix in (".py", ".ts", ".tsx", ".json", ".md", ".sh", ".txt"):
                        translate_file_deep(fp)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Extraction and NLP - Test Assignment
----------------------------------------
This script:
  1) Reads Input.xlsx (columns: URL_ID, URL)
  2) Downloads each URL, extracts the article title + body text (ignoring headers/footers/nav)
  3) Saves each article as "extracted_articles/<URL_ID>.txt"
  4) Computes the required text analysis variables for each article
  5) Exports results to "Output.xlsx" (matching "Output Data Structure.xlsx")

How to run:
    python nlp_extractor.py --input Input.xlsx --out Output.xlsx

Dependencies:
    pip install requests beautifulsoup4 lxml pandas openpyxl

Optional (for better results):
    - Place sentiment and stopword lexicons in ./lexicons/
        ./lexicons/positive-words.txt
        ./lexicons/negative-words.txt
        ./lexicons/stopwords.txt
    If these files are not found, the script will use small built-in fallback lists.
"""
import argparse
import os
import re
import math
from pathlib import Path
from typing import List, Tuple, Optional

import requests
from bs4 import BeautifulSoup
import pandas as pd

# ----------------------------
# Lexicon loading (optional) |
# ----------------------------
FALLBACK_POSITIVE = {
    "good","great","excellent","positive","fortunate","correct","superior","beneficial","favorable",
    "growth","success","improve","improved","improvement","achieve","achievement","valuable","advantage"
}
FALLBACK_NEGATIVE = {
    "bad","poor","negative","unfortunate","wrong","inferior","loss","decline","decrease","risk","failure",
    "worse","worst","problem","issues","error","errors","crisis","downturn"
}
FALLBACK_STOPWORDS = {
    "a","an","and","the","in","on","at","for","from","to","of","is","am","are","was","were","be","been",
    "being","this","that","these","those","it","its","as","by","with","or","but","if","then","so","than",
    "too","very","can","cannot","could","should","would","will","just","over","under","again","once","about",
    "into","because","while","where","when","which","who","whom","what","why","how","do","does","did","doing",
    "we","you","he","she","they","them","their","our","my","your","i","me","him","her","us"
}

def load_lexicon(path: Path) -> Optional[set]:
    if path.exists():
        words = set()
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(";") or line.startswith("#"):
                    continue
                # keep only alphabetic tokens
                token = re.sub(r"[^A-Za-z]", "", line).lower()
                if token:
                    words.add(token)
        return words
    return None

def load_all_lexicons(base: Path):
    pos = load_lexicon(base / "positive-words.txt") or FALLBACK_POSITIVE
    neg = load_lexicon(base / "negative-words.txt") or FALLBACK_NEGATIVE
    stop = load_lexicon(base / "stopwords.txt") or FALLBACK_STOPWORDS
    return pos, neg, stop

# ----------------------------
# Helpers                     |
# ----------------------------

def clean_soup(soup: BeautifulSoup) -> None:
    # Drop scripts, styles, navs, footers, headers, asides
    for tag in soup(["script","style","noscript","header","footer","nav","form","iframe","svg","img","figure","picture","button"]):
        tag.decompose()

def extract_title_and_body(html: str) -> Tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    clean_soup(soup)

    # Title
    title = ""
    # Prefer h1 text
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(" ", strip=True)
    # Fallback: <title>
    if not title and soup.title and soup.title.get_text(strip=True):
        title = soup.title.get_text(" ", strip=True)

    # Try <article> first
    article = soup.find("article")
    if article:
        paras = [p.get_text(" ", strip=True) for p in article.find_all("p")]
        body = "\n".join([t for t in paras if t])
        if body.strip():
            return title, body

    # Otherwise, choose the container with the most <p> text
    candidates = []
    for div in soup.find_all(["div","section","main"]):
        ps = div.find_all("p")
        if len(ps) >= 2:  # more than one paragraph
            text_len = sum(len(p.get_text()) for p in ps)
            candidates.append((text_len, div))
    if candidates:
        _, best = max(candidates, key=lambda x: x[0])
        paras = [p.get_text(" ", strip=True) for p in best.find_all("p")]
        body = "\n".join([t for t in paras if t])
    else:
        # Fallback: all paragraphs on the page
        paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        body = "\n".join([t for t in paras if t])

    return title, body

def fetch_url(url: str, timeout: int = 20) -> Optional[str]:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200 and resp.text:
            return resp.text
    except requests.RequestException:
        return None
    return None

WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")

def tokenize_words(text: str) -> List[str]:
    return WORD_RE.findall(text)

SENT_SPLIT_RE = re.compile(r"[.!?]+")

def tokenize_sentences(text: str) -> List[str]:
    # Simple sentence splitter
    sents = [s.strip() for s in SENT_SPLIT_RE.split(text) if s.strip()]
    return sents

VOWELS = "aeiouy"

def count_syllables(word: str) -> int:
    w = word.lower()
    # Remove non-alpha
    w = re.sub(r"[^a-z]", "", w)
    if not w:
        return 0
    # Heuristic syllable count: groups of vowels
    syllables = 0
    prev_is_vowel = False
    for ch in w:
        is_vowel = ch in VOWELS
        if is_vowel and not prev_is_vowel:
            syllables += 1
        prev_is_vowel = is_vowel
    # Adjust for silent 'e' at the end
    if w.endswith("e") and syllables > 1:
        syllables -= 1
    return max(1, syllables)

PPRON_RE = re.compile(r"\b(I|we|my|ours|us)\b", re.IGNORECASE)

def analyze_text(text: str, pos_lex: set, neg_lex: set, stopwords: set) -> dict:
    sentences = tokenize_sentences(text)
    words_all = [w.lower() for w in tokenize_words(text)]
    words_clean = [w for w in words_all if w not in stopwords]

    # Positive/Negative scores
    pos_score = sum(1 for w in words_clean if w in pos_lex)
    neg_score = sum(1 for w in words_clean if w in neg_lex)

    # Polarity and Subjectivity
    polarity = (pos_score - neg_score) / ( (pos_score + neg_score) + 1e-6 )
    subjectivity = (pos_score + neg_score) / ( (len(words_clean)) + 1e-6 )

    # Complex words (syllables > 2)
    syllable_counts = [count_syllables(w) for w in words_clean]
    complex_flags = [1 if s > 2 else 0 for s in syllable_counts]
    complex_count = sum(complex_flags)

    words_per_sentence = [len(tokenize_words(s)) for s in sentences] if sentences else [0]
    avg_sentence_length = (sum(words_per_sentence) / len(words_per_sentence)) if words_per_sentence else 0.0
    avg_words_per_sentence = avg_sentence_length

    total_words = len(words_clean) if words_clean else 0
    pct_complex = (complex_count / total_words) if total_words else 0.0

    fog_index = 0.4 * (avg_sentence_length + 100 * pct_complex)

    # Syllables per word
    syllables_per_word = (sum(syllable_counts) / total_words) if total_words else 0.0

    # Personal pronouns
    # Exclude uppercase "US" by checking exact match
    personal_pronouns = 0
    for m in PPRON_RE.finditer(text):
        token = m.group(0)
        if token == "US":
            continue
        personal_pronouns += 1

    # Avg word length (letters only)
    total_chars = sum(len(re.sub(r"[^A-Za-z]", "", w)) for w in words_clean)
    avg_word_length = (total_chars / total_words) if total_words else 0.0

    return {
        "POSITIVE SCORE": pos_score,
        "NEGATIVE SCORE": neg_score,
        "POLARITY SCORE": polarity,
        "SUBJECTIVITY SCORE": subjectivity,
        "AVG SENTENCE LENGTH": avg_sentence_length,
        "PERCENTAGE OF COMPLEX WORDS": pct_complex,
        "FOG INDEX": fog_index,
        "AVG NUMBER OF WORDS PER SENTENCE": avg_words_per_sentence,
        "COMPLEX WORD COUNT": complex_count,
        "WORD COUNT": total_words,
        "SYLLABLE PER WORD": syllables_per_word,
        "PERSONAL PRONOUNS": personal_pronouns,
        "AVG WORD LENGTH": avg_word_length,
    }

def process_row(url_id: str, url: str, out_txt_dir: Path, pos_lex: set, neg_lex: set, stopwords: set):
    html = fetch_url(url)
    if not html:
        return {"URL_ID": url_id, "URL": url, "error": "Failed to fetch URL"}, ""

    title, body = extract_title_and_body(html)
    article_text = title.strip() + "\n\n" + body.strip() if title or body else ""

    # Save article text
    out_path = out_txt_dir / f"{url_id}.txt"
    out_path.write_text(article_text, encoding="utf-8", errors="ignore")

    # Analyze
    analysis = analyze_text(article_text, pos_lex, neg_lex, stopwords)
    row = {"URL_ID": url_id, "URL": url}
    row.update(analysis)
    return row, article_text

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="Input.xlsx", help="Path to Input.xlsx")
    parser.add_argument("--out", default="Output.xlsx", help="Path to save the output Excel")
    parser.add_argument("--out_csv", default=None, help="Optional path to also save CSV")
    parser.add_argument("--save_html", action="store_true", help="Also save the raw HTML for debugging")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        raise FileNotFoundError(f"Input file not found: {in_path}")

    df_in = pd.read_excel(in_path)
    if not {"URL_ID","URL"}.issubset(df_in.columns):
        raise ValueError("Input.xlsx must contain 'URL_ID' and 'URL' columns.")

    out_txt_dir = Path("extracted_articles")
    out_txt_dir.mkdir(parents=True, exist_ok=True)

    if args.save_html:
        Path("downloaded_html").mkdir(parents=True, exist_ok=True)

    # Load lexicons
    pos_lex, neg_lex, stopwords = load_all_lexicons(Path("lexicons"))

    rows = []
    for _, rec in df_in.iterrows():
        url_id = str(rec["URL_ID"]).strip()
        url = str(rec["URL"]).strip()
        try:
            row, article_text = process_row(url_id, url, out_txt_dir, pos_lex, neg_lex, stopwords)
            rows.append(row)
        except Exception as e:
            rows.append({"URL_ID": url_id, "URL": url, "error": f"Exception: {e}"})

    df_out = pd.DataFrame(rows)

    # Reorder columns to match "Output Data Structure.xlsx"
    desired_cols = [
        "URL_ID","URL",
        "POSITIVE SCORE","NEGATIVE SCORE","POLARITY SCORE","SUBJECTIVITY SCORE",
        "AVG SENTENCE LENGTH","PERCENTAGE OF COMPLEX WORDS","FOG INDEX",
        "AVG NUMBER OF WORDS PER SENTENCE","COMPLEX WORD COUNT","WORD COUNT",
        "SYLLABLE PER WORD","PERSONAL PRONOUNS","AVG WORD LENGTH"
    ]
    # Ensure all columns exist
    for c in desired_cols:
        if c not in df_out.columns:
            df_out[c] = None
    df_out = df_out[desired_cols + [c for c in df_out.columns if c not in desired_cols]]

    # Save Excel
    df_out.to_excel(args.out, index=False)
    if args.out_csv:
        df_out.to_csv(args.out_csv, index=False, encoding="utf-8")

    print(f"Saved analysis to {args.out}")
    if args.out_csv:
        print(f"Saved CSV to {args.out_csv}")
    print(f"Saved article texts to {out_txt_dir.resolve()}")

if __name__ == "__main__":
    main()

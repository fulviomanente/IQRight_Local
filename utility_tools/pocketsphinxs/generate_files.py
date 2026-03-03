#!/usr/bin/env python3
"""
generate_pocketsphinx_files.py

Reads a CSV file with columns: first, last (full names)
Deduplicates individual name tokens, generates:
  - names.dict      (pronunciation dictionary for PocketSphinx)
  - names.gram      (JSGF grammar file for PocketSphinx)
  - names_review.txt (human-readable review file for manual tweaking)

Uses CMU Pronouncing Dictionary (via 'pronouncing' package) for known words,
falls back to English phoneme rules for unknown names.

Install:
    pip install pronouncing

Usage:
    python3 generate_pocketsphinx_files.py names.csv

CSV format:
    first,last
    Maria,Garcia
    Jose Luis,Rodriguez
"""

import csv
import sys
import os
import re
from collections import OrderedDict

try:
    import pronouncing
except ImportError:
    print("Error: 'pronouncing' package required.")
    print("Install: pip install pronouncing")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 1. CMU Dictionary Lookup
# ---------------------------------------------------------------------------
def lookup_cmu(word):
    """
    Look up a word in CMU Pronouncing Dictionary.
    Returns list of phonemes (without stress markers) or None.
    """
    phones_list = pronouncing.phones_for_word(word.lower())
    if phones_list:
        phones = phones_list[0]
        cleaned = re.sub(r'\d', '', phones)
        return cleaned.split()
    return None


# ---------------------------------------------------------------------------
# 2. Rule-Based English Phoneme Generator (for names not in CMU)
# ---------------------------------------------------------------------------
def english_g2p(word):
    """
    Rule-based grapheme-to-phoneme conversion optimized for
    anglicized Spanish/Portuguese names.
    """
    w = word.lower().strip()
    phones = []
    i = 0
    length = len(w)

    while i < length:
        # Trigraphs
        if i + 2 < length:
            tri = w[i:i+3]
            if tri == 'tch': phones.append('CH'); i += 3; continue
            if tri == 'ght': phones.append('T'); i += 3; continue
            if tri == 'sch': phones.append('SH'); i += 3; continue

        # Digraphs
        if i + 1 < length:
            di = w[i:i+2]
            if di == 'ch': phones.append('CH'); i += 2; continue
            if di == 'sh': phones.append('SH'); i += 2; continue
            if di == 'th': phones.append('TH'); i += 2; continue
            if di == 'ph': phones.append('F'); i += 2; continue
            if di == 'wh': phones.append('W'); i += 2; continue
            if di == 'gh':
                if i == 0: phones.append('G')
                i += 2; continue
            if di == 'gn':
                phones.append('N'); i += 2; continue
            if di == 'kn': phones.append('N'); i += 2; continue
            if di == 'wr': phones.append('R'); i += 2; continue
            if di == 'ck': phones.append('K'); i += 2; continue
            if di == 'ng': phones.append('NG'); i += 2; continue
            if di == 'qu': phones.extend(['K', 'W']); i += 2; continue
            # Double consonants
            if di in ('ll','rr','ss','tt','zz','ff','nn','mm','pp','bb','dd','gg'):
                single_map = {'ll':'L','rr':'R','ss':'S','tt':'T','zz':'Z',
                              'ff':'F','nn':'N','mm':'M','pp':'P','bb':'B',
                              'dd':'D','gg':'G'}
                phones.append(single_map[di]); i += 2; continue
            if di == 'cc': phones.extend(['K','S']); i += 2; continue
            # Vowel digraphs
            if di == 'ee': phones.append('IY'); i += 2; continue
            if di == 'ea': phones.append('IY'); i += 2; continue
            if di == 'oo': phones.append('UW'); i += 2; continue
            if di == 'ou': phones.append('AW'); i += 2; continue
            if di == 'ow':
                phones.append('OW' if i + 2 >= length else 'AW')
                i += 2; continue
            if di in ('oi','oy'): phones.append('OY'); i += 2; continue
            if di in ('ai','ay'): phones.append('EY'); i += 2; continue
            if di in ('au','aw'): phones.append('AO'); i += 2; continue
            if di in ('ei','ey'): phones.append('EY'); i += 2; continue
            if di == 'ie': phones.append('IY'); i += 2; continue
            if di == 'ue': phones.append('UW'); i += 2; continue

        ch = w[i]

        # Silent final 'e'
        if ch == 'e' and i == length - 1 and length > 2:
            i += 1; continue

        # Vowels with magic-e check
        if ch == 'a':
            if i + 2 < length and w[i+2] == 'e' and w[i+1] not in 'aeiou':
                phones.append('EY')
            else:
                phones.append('AE')
            i += 1; continue
        if ch == 'e':
            if i + 2 < length and w[i+2] == 'e' and w[i+1] not in 'aeiou':
                phones.append('IY')
            else:
                phones.append('EH')
            i += 1; continue
        if ch == 'i':
            if i + 2 < length and w[i+2] == 'e' and w[i+1] not in 'aeiou':
                phones.append('AY')
            else:
                phones.append('IH')
            i += 1; continue
        if ch == 'o':
            if i + 2 < length and w[i+2] == 'e' and w[i+1] not in 'aeiou':
                phones.append('OW')
            else:
                phones.append('AA')
            i += 1; continue
        if ch == 'u':
            if i + 2 < length and w[i+2] == 'e' and w[i+1] not in 'aeiou':
                phones.append('UW')
            else:
                phones.append('AH')
            i += 1; continue
        if ch == 'y':
            phones.append('Y' if i == 0 else 'IY')
            i += 1; continue

        # Simple consonants
        cmap = {'b':'B','d':'D','f':'F','h':'HH','k':'K','l':'L',
                'm':'M','n':'N','p':'P','r':'R','t':'T','v':'V',
                'w':'W','z':'Z'}
        if ch in cmap:
            phones.append(cmap[ch]); i += 1; continue

        # Context-sensitive consonants
        if ch == 'c':
            phones.append('S' if (i+1 < length and w[i+1] in 'eiy') else 'K')
            i += 1; continue
        if ch == 'g':
            phones.append('JH' if (i+1 < length and w[i+1] in 'ei') else 'G')
            i += 1; continue
        if ch == 'j':
            phones.append('JH'); i += 1; continue
        if ch == 'x':
            phones.extend(['K','S']); i += 1; continue
        if ch == 's':
            if (i > 0 and i+1 < length and w[i-1] in 'aeiou' and w[i+1] in 'aeiou'):
                phones.append('Z')
            else:
                phones.append('S')
            i += 1; continue

        i += 1  # skip unrecognized chars

    return phones


# ---------------------------------------------------------------------------
# 3. Parse CSV and deduplicate
# ---------------------------------------------------------------------------
def parse_csv(filepath):
    """Read CSV, return full_names, unique first tokens, unique last tokens."""
    full_names = []
    first_names = set()
    last_names = set()

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            print("Error: CSV file appears to be empty."); sys.exit(1)

        col_map = {}
        for col in reader.fieldnames:
            c = col.strip().lower()
            if c in ('first','first_name','firstname','first name','name'):
                col_map['first'] = col
            elif c in ('last','last_name','lastname','last name','surname'):
                col_map['last'] = col

        if 'first' not in col_map or 'last' not in col_map:
            print(f"Error: Could not find 'first' and 'last' columns.")
            print(f"       Found columns: {reader.fieldnames}")
            sys.exit(1)

        for row in reader:
            first_raw = row[col_map['first']].strip()
            last_raw = row[col_map['last']].strip()
            if not first_raw or not last_raw: continue

            full_names.append((first_raw, last_raw))

            for token in first_raw.lower().split():
                t = re.sub(r'[^a-z]', '', token)
                if t: first_names.add(t)
            for token in last_raw.lower().split():
                t = re.sub(r'[^a-z]', '', token)
                if t: last_names.add(t)

    return full_names, sorted(first_names), sorted(last_names)


# ---------------------------------------------------------------------------
# 4. Generate pronunciation dictionary
# ---------------------------------------------------------------------------
def generate_dict(unique_tokens, output_path):
    entries = OrderedDict()
    cmu_hits = 0
    rule_hits = 0

    for token in sorted(unique_tokens):
        phones = lookup_cmu(token)
        if phones:
            entries[token] = ' '.join(phones)
            cmu_hits += 1
        else:
            phones = english_g2p(token)
            entries[token] = ' '.join(phones)
            rule_hits += 1

    with open(output_path, 'w', encoding='utf-8') as f:
        for word, phones in entries.items():
            f.write(f"{word} {phones}\n")

    print(f"\nDictionary generation summary:")
    print(f"  Total unique tokens:    {len(unique_tokens)}")
    print(f"  Found in CMU dict:      {cmu_hits}")
    print(f"  Generated by rules:     {rule_hits}")
    print(f"  Written to: {output_path}")
    return entries


# ---------------------------------------------------------------------------
# 5. Generate JSGF grammar file
# ---------------------------------------------------------------------------
def generate_grammar(unique_firsts, unique_lasts, full_names, output_path):
    first_patterns = set()
    last_patterns = set()

    for first_raw, last_raw in full_names:
        f_clean = re.sub(r'[^a-zA-Z\s]', '', first_raw).lower().strip()
        l_clean = re.sub(r'[^a-zA-Z\s]', '', last_raw).lower().strip()
        if f_clean: first_patterns.add(f_clean)
        if l_clean: last_patterns.add(l_clean)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#JSGF V1.0;\n")
        f.write("grammar names;\n\n")
        f.write("<first> = " + "\n       | ".join(sorted(first_patterns)) + ";\n\n")
        f.write("<last> = " + "\n      | ".join(sorted(last_patterns)) + ";\n\n")
        f.write("public <fullname> = <first> <last>;\n")

    print(f"\nGrammar generation summary:")
    print(f"  Unique first name patterns: {len(first_patterns)}")
    print(f"  Unique last name patterns:  {len(last_patterns)}")
    print(f"  Possible combinations:      {len(first_patterns) * len(last_patterns)}")
    print(f"  Actual names in list:        {len(full_names)}")
    print(f"  Written to: {output_path}")


# ---------------------------------------------------------------------------
# 6. Generate review file
# ---------------------------------------------------------------------------
def generate_review_file(entries, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=" * 65 + "\n")
        f.write("  PRONUNCIATION REVIEW FILE\n")
        f.write("=" * 65 + "\n")
        f.write("  Edit names.dict directly for any corrections.\n\n")
        f.write("  ARPAbet quick reference:\n")
        f.write("  VOWELS:  AA=father  AE=cat  AH=but  AO=dog   AW=cow   AY=my\n")
        f.write("           EH=bed     ER=bird EY=say  IH=bit   IY=see\n")
        f.write("           OW=go      OY=boy  UH=book UW=too\n")
        f.write("  CONSONANTS: B CH D DH F G HH JH K L M N NG P R S\n")
        f.write("              SH T TH V W Y Z ZH\n")
        f.write("=" * 65 + "\n\n")
        f.write(f"  {'WORD':20s}    {'SOURCE':6s}    PHONEMES\n")
        f.write(f"  {'-'*20}    {'-'*6}    {'-'*30}\n")

        for word, phones in sorted(entries.items()):
            source = "CMU" if lookup_cmu(word) else "RULES"
            f.write(f"  {word:20s}    {source:6s}    {phones}\n")

    print(f"  Review file: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_pocketsphinx_files.py <names.csv>")
        print()
        print("CSV format:")
        print("  first,last")
        print("  Maria,Garcia")
        print("  Jose Luis,Rodriguez")
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"Error: File not found: {csv_path}"); sys.exit(1)

    out_dir = os.path.dirname(os.path.abspath(csv_path))
    dict_path = os.path.join(out_dir, "names.dict")
    gram_path = os.path.join(out_dir, "names.gram")
    review_path = os.path.join(out_dir, "names_review.txt")

    print(f"Reading: {csv_path}")
    full_names, unique_firsts, unique_lasts = parse_csv(csv_path)
    print(f"  Total entries:         {len(full_names)}")
    print(f"  Unique first tokens:   {len(unique_firsts)}")
    print(f"  Unique last tokens:    {len(unique_lasts)}")

    all_tokens = sorted(set(unique_firsts + unique_lasts))
    print(f"  Total unique tokens:   {len(all_tokens)}")

    entries = generate_dict(all_tokens, dict_path)
    generate_grammar(unique_firsts, unique_lasts, full_names, gram_path)
    generate_review_file(entries, review_path)

    print("\n" + "=" * 60)
    print("  DONE! Next steps:")
    print("=" * 60)
    print(f"  1. Review pronunciations: {review_path}")
    print(f"  2. Edit {dict_path} for corrections")
    print(f"  3. Test with PocketSphinx:")
    print(f"     pocketsphinx_continuous -jsgf {gram_path} -dict {dict_path}")
    print()
    print(f"  Raspberry Pi Zero setup:")
    print(f"     sudo apt install pocketsphinx pocketsphinx-en-us")
    print(f"     pip3 install pocketsphinx pronouncing")


if __name__ == '__main__':
    main()
"""
matching_engine.py

Hybrid phonetic + fuzzy matching engine for student name lookup.
Combines Double Metaphone, Soundex-style matching, and Levenshtein
distance to find the best student matches from a spoken or typed query.

Even with 37% voice accuracy, phonetic similarity often surfaces
the correct name in the top 5-8 results.
"""

import re
import pandas as pd
from metaphone import doublemetaphone
from rapidfuzz import fuzz, process


class StudentMatcher:
    """
    Loads a student list and provides fast phonetic + fuzzy matching.

    Usage:
        matcher = StudentMatcher("students.txt")
        results = matcher.search("rod reeg ez")  # voice mangled "Rodriguez"
        # Returns ranked list of (student_name, score) tuples
    """

    def __init__(self, filepath, first_col="first", last_col="last"):
        """
        Load student list from CSV/TSV/TXT file.
        Expects columns for first name and last name.
        """
        # Try to detect delimiter
        if filepath.endswith(".csv"):
            self.df = pd.read_csv(filepath, encoding="utf-8-sig")
        elif filepath.endswith(".tsv"):
            self.df = pd.read_csv(filepath, sep="\t", encoding="utf-8-sig")
        else:
            # Try comma first, then tab
            try:
                self.df = pd.read_csv(filepath, encoding="utf-8-sig")
            except Exception:
                self.df = pd.read_csv(filepath, sep="\t", encoding="utf-8-sig")

        # Flexible column matching
        col_map = {}
        for col in self.df.columns:
            c = col.strip().lower()
            if c in ("first", "first_name", "firstname", "first name", "name"):
                col_map["first"] = col
            elif c in ("last", "last_name", "lastname", "last name", "surname"):
                col_map["last"] = col

        if "first" not in col_map or "last" not in col_map:
            raise ValueError(
                f"Could not find first/last columns. Found: {list(self.df.columns)}"
            )

        self.df["first_clean"] = self.df[col_map["first"]].str.strip().str.lower()
        self.df["last_clean"] = self.df[col_map["last"]].str.strip().str.lower()
        self.df["full_name"] = (
            self.df[col_map["first"]].str.strip()
            + " "
            + self.df[col_map["last"]].str.strip()
        )
        self.df["full_clean"] = self.df["full_name"].str.lower()

        # Pre-compute metaphone codes for every name
        self._build_phonetic_index()

        print(f"Loaded {len(self.df)} students")

    def _build_phonetic_index(self):
        """Pre-compute Double Metaphone codes for fast phonetic matching."""
        self.phonetic_index = []

        for idx, row in self.df.iterrows():
            first = row["first_clean"]
            last = row["last_clean"]
            full = row["full_clean"]

            # Generate metaphone codes for individual tokens and full name
            first_tokens = first.split()
            last_tokens = last.split()
            all_tokens = first_tokens + last_tokens

            meta_codes = set()
            for token in all_tokens:
                primary, secondary = doublemetaphone(token)
                if primary:
                    meta_codes.add(primary)
                if secondary:
                    meta_codes.add(secondary)

            self.phonetic_index.append(
                {
                    "idx": idx,
                    "first": first,
                    "last": last,
                    "full": full,
                    "display": row["full_name"],
                    "first_tokens": first_tokens,
                    "last_tokens": last_tokens,
                    "all_tokens": all_tokens,
                    "meta_codes": meta_codes,
                }
            )

    def _phonetic_score(self, query_tokens, entry):
        """
        Score how phonetically similar the query is to a student entry.
        Returns 0-100 score.
        """
        if not query_tokens:
            return 0

        query_meta = set()
        for token in query_tokens:
            primary, secondary = doublemetaphone(token)
            if primary:
                query_meta.add(primary)
            if secondary:
                query_meta.add(secondary)

        if not query_meta or not entry["meta_codes"]:
            return 0

        # Count matching metaphone codes
        matches = query_meta & entry["meta_codes"]
        if not matches:
            return 0

        # Score based on proportion of query codes matched
        match_ratio = len(matches) / len(query_meta)

        # Bonus if the entry also has a high proportion matched
        entry_ratio = len(matches) / len(entry["meta_codes"])

        score = (match_ratio * 70) + (entry_ratio * 30)
        return min(score, 100)

    def _fuzzy_score(self, query, entry):
        """
        Fuzzy string matching score using multiple strategies.
        Returns 0-100 score.
        """
        query_lower = query.lower().strip()
        full = entry["full"]

        # Full name fuzzy ratio
        full_ratio = fuzz.token_sort_ratio(query_lower, full)

        # Partial matching (handles when query is just first or last name)
        partial_ratio = fuzz.partial_ratio(query_lower, full)

        # Token-level matching
        token_ratio = fuzz.token_set_ratio(query_lower, full)

        # Best of partial and token, weighted with full
        score = max(
            full_ratio,
            (partial_ratio * 0.8),
            (token_ratio * 0.9),
        )

        return score

    def _first_name_boost(self, query_tokens, entry):
        """
        Extra boost when a query token closely matches a first name.
        Helps disambiguate when voice garbles the last name.
        """
        if not query_tokens:
            return 0

        boost = 0
        for qt in query_tokens:
            for ft in entry["first_tokens"]:
                ratio = fuzz.ratio(qt, ft)
                if ratio > 80:
                    boost = max(boost, ratio * 0.15)
            for lt in entry["last_tokens"]:
                ratio = fuzz.ratio(qt, lt)
                if ratio > 80:
                    boost = max(boost, ratio * 0.15)

        return boost

    def search(self, query, top_n=8, mode="hybrid"):
        """
        Search for students matching a query string.

        Args:
            query: The search string (from voice or text input)
            top_n: Number of results to return
            mode: "hybrid" (phonetic + fuzzy), "text" (fuzzy only),
                  "phonetic" (phonetic only)

        Returns:
            List of dicts: [{"name": "...", "score": 0-100, "idx": N}, ...]
        """
        if not query or not query.strip():
            return []

        query_clean = re.sub(r"[^a-zA-Z\s]", "", query).lower().strip()
        query_tokens = query_clean.split()

        results = []

        for entry in self.phonetic_index:
            if mode == "text":
                score = self._fuzzy_score(query_clean, entry)
            elif mode == "phonetic":
                score = self._phonetic_score(query_tokens, entry)
            else:
                # Hybrid: weighted combination
                phon_score = self._phonetic_score(query_tokens, entry)
                fuzz_score = self._fuzzy_score(query_clean, entry)
                boost = self._first_name_boost(query_tokens, entry)

                # Weighted blend - fuzzy gets more weight because even
                # garbled voice output has partial string similarity
                score = (phon_score * 0.4) + (fuzz_score * 0.6) + boost

            if score > 20:  # minimum threshold
                results.append(
                    {
                        "name": entry["display"],
                        "score": round(min(score, 100), 1),
                        "idx": entry["idx"],
                    }
                )

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:top_n]

    def search_by_field(self, query, field="last", top_n=8):
        """
        Search only first names or only last names.

        Args:
            query: Search string
            field: "first" or "last"
            top_n: Number of results
        """
        if not query or not query.strip():
            return []

        query_clean = re.sub(r"[^a-zA-Z\s]", "", query).lower().strip()

        results = []
        for entry in self.phonetic_index:
            target = entry["first"] if field == "first" else entry["last"]

            # Fuzzy match against the specific field
            ratio = fuzz.token_sort_ratio(query_clean, target)
            partial = fuzz.partial_ratio(query_clean, target)
            score = max(ratio, partial * 0.9)

            # Phonetic match on the field tokens
            query_tokens = query_clean.split()
            target_tokens = (
                entry["first_tokens"] if field == "first" else entry["last_tokens"]
            )
            for qt in query_tokens:
                qp, qs = doublemetaphone(qt)
                for tt in target_tokens:
                    tp, ts = doublemetaphone(tt)
                    if qp and tp and qp == tp:
                        score += 15
                    elif qs and ts and qs == ts:
                        score += 8

            if score > 25:
                results.append(
                    {"name": entry["display"], "score": round(min(score, 100), 1), "idx": entry["idx"]}
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_n]

    def get_all_students(self):
        """Return all students sorted alphabetically by last name."""
        return sorted(
            [e["display"] for e in self.phonetic_index],
            key=lambda x: x.split()[-1].lower(),
        )


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python matching_engine.py <students.csv> [query]")
        sys.exit(1)

    matcher = StudentMatcher(sys.argv[1])

    if len(sys.argv) >= 3:
        query = " ".join(sys.argv[2:])
        print(f"\nSearching for: '{query}'")
        print("-" * 50)
        results = matcher.search(query)
        for r in results:
            print(f"  {r['score']:5.1f}  {r['name']}")
    else:
        # Interactive mode
        print("\nInteractive search (type 'q' to quit):")
        while True:
            query = input("\nSearch: ").strip()
            if query.lower() == "q":
                break
            results = matcher.search(query)
            if results:
                for i, r in enumerate(results):
                    print(f"  [{i+1}] {r['score']:5.1f}  {r['name']}")
            else:
                print("  No matches found.")

"""
matching_engine.py

Hybrid phonetic + fuzzy matching engine for student name lookup.
Combines Double Metaphone and Levenshtein distance to find the best
student matches from a typed query on the scanner touchscreen.

Adapted for scanner use: returns DeviceID and Grade alongside matches.
"""

import re
import pandas as pd
from metaphone import doublemetaphone
from rapidfuzz import fuzz


class StudentMatcher:
    """
    Loads a student list and provides fast phonetic + fuzzy matching.

    Usage:
        matcher = StudentMatcher("data/students.csv")
        results = matcher.search_by_field("smith", field="last")
        # Returns: [{"name": "Anna Smith", "device_id": "P27810777", "grade": "4P", "score": 95.0}, ...]
    """

    def __init__(self, filepath: str):
        """Load student list from CSV file with columns: FirstName, LastName, DeviceID, Grade."""
        self.df = pd.read_csv(filepath, encoding="utf-8-sig")

        # Map columns flexibly
        col_map = {}
        for col in self.df.columns:
            c = col.strip().lower()
            if c in ("first", "first_name", "firstname", "first name"):
                col_map["first"] = col
            elif c in ("last", "last_name", "lastname", "last name", "surname"):
                col_map["last"] = col
            elif c in ("deviceid", "device_id", "qrcode", "qr_code", "code"):
                col_map["device_id"] = col
            elif c in ("grade", "class", "classroom", "classcode", "class_code"):
                col_map["grade"] = col

        if "first" not in col_map or "last" not in col_map:
            raise ValueError(f"Could not find first/last columns. Found: {list(self.df.columns)}")

        self._first_col = col_map["first"]
        self._last_col = col_map["last"]
        self._device_col = col_map.get("device_id")
        self._grade_col = col_map.get("grade")

        self.df["first_clean"] = self.df[self._first_col].str.strip().str.lower()
        self.df["last_clean"] = self.df[self._last_col].str.strip().str.lower()
        self.df["full_name"] = (
            self.df[self._first_col].str.strip() + " " + self.df[self._last_col].str.strip()
        )
        self.df["full_clean"] = self.df["full_name"].str.lower()

        self._build_phonetic_index()

    def _build_phonetic_index(self):
        """Pre-compute Double Metaphone codes for fast phonetic matching."""
        self.phonetic_index = []

        for idx, row in self.df.iterrows():
            first_tokens = row["first_clean"].split()
            last_tokens = row["last_clean"].split()

            meta_codes = set()
            for token in first_tokens + last_tokens:
                primary, secondary = doublemetaphone(token)
                if primary:
                    meta_codes.add(primary)
                if secondary:
                    meta_codes.add(secondary)

            entry = {
                "idx": idx,
                "first": row["first_clean"],
                "last": row["last_clean"],
                "full": row["full_clean"],
                "display": row["full_name"],
                "first_tokens": first_tokens,
                "last_tokens": last_tokens,
                "meta_codes": meta_codes,
                "device_id": str(row[self._device_col]).strip() if self._device_col else "",
                "grade": str(row[self._grade_col]).strip() if self._grade_col else "",
            }
            self.phonetic_index.append(entry)

    def _phonetic_score(self, query_tokens: list, entry: dict) -> float:
        """Score how phonetically similar the query is to a student entry (0-100)."""
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

        matches = query_meta & entry["meta_codes"]
        if not matches:
            return 0

        match_ratio = len(matches) / len(query_meta)
        entry_ratio = len(matches) / len(entry["meta_codes"])
        return min((match_ratio * 70) + (entry_ratio * 30), 100)

    def _fuzzy_score(self, query: str, entry: dict) -> float:
        """Fuzzy string matching score using multiple strategies (0-100)."""
        query_lower = query.lower().strip()
        full = entry["full"]

        full_ratio = fuzz.token_sort_ratio(query_lower, full)
        partial_ratio = fuzz.partial_ratio(query_lower, full)
        token_ratio = fuzz.token_set_ratio(query_lower, full)

        return max(full_ratio, partial_ratio * 0.8, token_ratio * 0.9)

    def _first_name_boost(self, query_tokens: list, entry: dict) -> float:
        """Extra boost when a query token closely matches a name token."""
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

    def search(self, query: str, top_n: int = 8, mode: str = "text") -> list:
        """
        Search for students matching a query string.

        Returns:
            List of dicts with name, device_id, grade, score
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
                phon_score = self._phonetic_score(query_tokens, entry)
                fuzz_score = self._fuzzy_score(query_clean, entry)
                boost = self._first_name_boost(query_tokens, entry)
                score = (phon_score * 0.4) + (fuzz_score * 0.6) + boost

            if score > 20:
                results.append({
                    "name": entry["display"],
                    "device_id": entry["device_id"],
                    "grade": entry["grade"],
                    "score": round(min(score, 100), 1),
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_n]

    def search_by_field(self, query: str, field: str = "last", top_n: int = 8) -> list:
        """
        Search only first names or only last names.

        Returns:
            List of dicts with name, device_id, grade, score
        """
        if not query or not query.strip():
            return []

        query_clean = re.sub(r"[^a-zA-Z\s]", "", query).lower().strip()

        results = []
        for entry in self.phonetic_index:
            target = entry["first"] if field == "first" else entry["last"]

            ratio = fuzz.token_sort_ratio(query_clean, target)
            partial = fuzz.partial_ratio(query_clean, target)
            score = max(ratio, partial * 0.9)

            # Phonetic boost
            query_tokens = query_clean.split()
            target_tokens = entry["first_tokens"] if field == "first" else entry["last_tokens"]
            for qt in query_tokens:
                qp, qs = doublemetaphone(qt)
                for tt in target_tokens:
                    tp, ts = doublemetaphone(tt)
                    if qp and tp and qp == tp:
                        score += 15
                    elif qs and ts and qs == ts:
                        score += 8

            if score > 25:
                results.append({
                    "name": entry["display"],
                    "device_id": entry["device_id"],
                    "grade": entry["grade"],
                    "score": round(min(score, 100), 1),
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_n]

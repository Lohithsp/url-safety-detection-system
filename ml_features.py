"""URL feature extraction and explanation helpers."""

from __future__ import annotations

import math
import re
from collections import Counter
from urllib.parse import parse_qs, urlparse

import pandas as pd


SUSPICIOUS_KEYWORDS = (
    "login", "signin", "verify", "secure", "account", "update", "reset",
    "bank", "wallet", "crypto", "paypal", "bonus", "claim", "free", "gift",
    "reward", "prize", "confirm", "password", "auth", "support",
)

SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly",
    "cutt.ly", "rebrand.ly", "shorturl.at", "s.id", "lnkd.in",
}

FEATURE_NAMES = [
    "url_length",
    "domain_length",
    "path_length",
    "query_length",
    "tld_length",
    "num_dots",
    "num_hyphens",
    "num_underscore",
    "num_slash",
    "num_question",
    "num_equal",
    "num_at",
    "num_ampersand",
    "num_percent",
    "num_digits",
    "digit_ratio",
    "num_letters",
    "letter_ratio",
    "special_char_count",
    "special_char_ratio",
    "num_subdomains",
    "is_https",
    "is_ip",
    "has_port",
    "has_punycode",
    "has_shortener",
    "suspicious_keyword_count",
    "has_suspicious_keyword",
    "login_keyword_count",
    "encoded_char_count",
    "redirect_keyword_count",
    "query_param_count",
    "url_entropy",
]


def normalize_url(url: str) -> str:
    url = str(url or "").strip()
    if url and not re.match(r"^[a-z][a-z0-9+.-]*://", url, flags=re.I):
        url = "https://" + url
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host.startswith("www."):
            new_host = host[4:]
            netloc = parsed.netloc
            if ":" in netloc:
                parts = netloc.split(":")
                if parts[-1].isdigit():
                    new_netloc = f"{new_host}:{parts[-1]}"
                else:
                    new_netloc = new_host
            else:
                new_netloc = new_host
            parsed = parsed._replace(netloc=new_netloc)
            url = urlunparse(parsed)
    except Exception:
        pass
    return url


def _entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    total = len(value)
    return float(-sum((count / total) * math.log2(count / total) for count in counts.values()))


def _is_ip(host: str) -> int:
    return int(bool(re.fullmatch(r"(\d{1,3}\.){3}\d{1,3}", host or "")))


def extract_url_features(url: str) -> dict[str, float]:
    url = normalize_url(url)
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    query = parsed.query or ""
    labels = [part for part in host.split(".") if part]
    tld = labels[-1] if labels else ""
    lowered = url.lower()
    keyword_hits = sum(1 for word in SUSPICIOUS_KEYWORDS if word in lowered)
    login_hits = sum(1 for word in ("login", "signin", "verify", "secure", "auth") if word in lowered)
    redirect_hits = sum(1 for word in ("redirect", "url=", "next=", "goto=", "return=", "dest=") if word in lowered)
    letters = sum(ch.isalpha() for ch in url)
    digits = sum(ch.isdigit() for ch in url)
    specials = sum(not ch.isalnum() for ch in url)
    length = max(len(url), 1)

    return {
        "url_length": len(url),
        "domain_length": len(host),
        "path_length": len(path),
        "query_length": len(query),
        "tld_length": len(tld),
        "num_dots": url.count("."),
        "num_hyphens": url.count("-"),
        "num_underscore": url.count("_"),
        "num_slash": url.count("/"),
        "num_question": url.count("?"),
        "num_equal": url.count("="),
        "num_at": url.count("@"),
        "num_ampersand": url.count("&"),
        "num_percent": url.count("%"),
        "num_digits": digits,
        "digit_ratio": digits / length,
        "num_letters": letters,
        "letter_ratio": letters / length,
        "special_char_count": specials,
        "special_char_ratio": specials / length,
        "num_subdomains": max(len(labels) - 2, 0),
        "is_https": int(parsed.scheme.lower() == "https"),
        "is_ip": _is_ip(host),
        "has_port": int(parsed.port is not None) if host else 0,
        "has_punycode": int("xn--" in host),
        "has_shortener": int(host in SHORTENERS or any(host.endswith("." + s) for s in SHORTENERS)),
        "suspicious_keyword_count": keyword_hits,
        "has_suspicious_keyword": int(keyword_hits > 0),
        "login_keyword_count": login_hits,
        "encoded_char_count": len(re.findall(r"%[0-9a-f]{2}", url, flags=re.I)),
        "redirect_keyword_count": redirect_hits,
        "query_param_count": len(parse_qs(query)),
        "url_entropy": _entropy(url),
    }


def url_risk_score(url: str) -> float:
    features = extract_url_features(url)
    return (
        features["has_suspicious_keyword"] * 2
        + features["has_shortener"] * 3
        + features["is_ip"] * 3
        + features["num_at"] * 2
        + features["num_subdomains"]
        + int(features["url_length"] > 100)
        + int(features["special_char_ratio"] > 0.25)
        + features["redirect_keyword_count"]
    )


def features_from_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    url_col = next((c for c in df.columns if c.lower() in {"url", "link"}), None)
    if url_col:
        urls = df[url_col].fillna("").astype(str)
        unique_features = {url: extract_url_features(url) for url in urls.drop_duplicates()}
        features = pd.DataFrame([unique_features[url] for url in urls], index=df.index)
    else:
        features = pd.DataFrame(0.0, index=df.index, columns=FEATURE_NAMES)
        rename_map = {
            "URLLength": "url_length",
            "length": "url_length",
            "url_length": "url_length",
            "DomainLength": "domain_length",
            "TLDLength": "tld_length",
            "NoOfSubDomain": "num_subdomains",
            "IsHTTPS": "is_https",
            "IsDomainIP": "is_ip",
            "NoOfDegitsInURL": "num_digits",
            "DegitRatioInURL": "digit_ratio",
            "NoOfLettersInURL": "num_letters",
            "LetterRatioInURL": "letter_ratio",
            "NoOfOtherSpecialCharsInURL": "special_char_count",
            "SpacialCharRatioInURL": "special_char_ratio",
            "NoOfQMarkInURL": "num_question",
            "NoOfEqualsInURL": "num_equal",
            "NoOfAmpersandInURL": "num_ampersand",
            "n_dots": "num_dots",
            "n_hypens": "num_hyphens",
            "n_underline": "num_underscore",
            "n_slash": "num_slash",
            "n_questionmark": "num_question",
            "n_equal": "num_equal",
            "n_at": "num_at",
            "n_and": "num_ampersand",
            "n_percent": "num_percent",
            "n_redirection": "redirect_keyword_count",
        }
        for source, target in rename_map.items():
            if source in df.columns:
                features[target] = pd.to_numeric(df[source], errors="coerce")

    return features.reindex(columns=FEATURE_NAMES)


def human_feature_reason(feature: str, value: float, direction: str = "high") -> str:
    reason_map = {
        "suspicious_keyword_count": "Contains suspicious keyword patterns",
        "has_suspicious_keyword": "Contains suspicious keyword patterns",
        "login_keyword_count": "Uses login, verify, secure, or authentication wording",
        "url_length": "Unusually long URL",
        "path_length": "Unusually long URL path",
        "query_length": "Long query string with extra parameters",
        "special_char_count": "Multiple special characters detected",
        "special_char_ratio": "Abnormal special-character ratio",
        "num_slash": "Many path separators detected",
        "num_dots": "Many dots detected in the URL",
        "num_hyphens": "Multiple hyphens found in the URL",
        "num_question": "Question mark indicates query parameters",
        "num_equal": "Parameter assignment detected in the URL",
        "num_ampersand": "Multiple query parameters detected",
        "num_percent": "Percent-encoded characters detected",
        "num_digits": "Many digits detected in the URL",
        "digit_ratio": "Abnormal digit ratio in the URL",
        "letter_ratio": "Abnormal letter ratio in the URL",
        "num_subdomains": "Suspicious domain structure with many subdomains",
        "is_ip": "Uses an IP address instead of a normal domain",
        "has_shortener": "Uses a URL shortener or redirect-style host",
        "num_at": "Contains an at-sign that can hide the real destination",
        "encoded_char_count": "Contains encoded characters often used for obfuscation",
        "redirect_keyword_count": "Contains redirect-style URL parameters",
        "url_entropy": "High randomness in URL characters",
        "is_https": "Normal HTTPS URL structure",
    }
    return reason_map.get(feature, f"Abnormal value for {feature.replace('_', ' ')}")

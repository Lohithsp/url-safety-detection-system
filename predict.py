"""Live URL prediction flow: extract features, predict, explain, optionally store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from explain import explain_url
from ml_features import normalize_url, extract_url_features


MODEL_PATH = Path(__file__).resolve().parent / "models" / "best_url_model.joblib"


def load_trusted_domains() -> set[str]:
    # Hardcoded base domains we always want to trust/check
    base_trusted = {
        "google.com", "gmail.com", "youtube.com", "googleapis.com", "gstatic.com", "googleusercontent.com",
        "microsoft.com", "live.com", "office.com", "outlook.com", "sharepoint.com", "visualstudio.com",
        "apple.com", "icloud.com", "apple-mapkit.com",
        "github.com", "githubusercontent.com", "github.io", "gitlab.com", "bitbucket.org",
        "chatgpt.com", "openai.com",
        "cloudflare.com", "cloudflarepages.com",
        "yahoo.com", "yimg.com",
        "adobe.com", "adobecc.com",
        "salesforce.com", "force.com",
        "dropbox.com", "slack.com", "zoom.us", "zoom.com",
        "baidu.com", "yandex.ru", "duckduckgo.com", "bing.com",
        "facebook.com", "instagram.com", "whatsapp.com", "fb.com", "messenger.com",
        "twitter.com", "x.com", "t.co", "linkedin.com", "licdn.com",
        "wikipedia.org", "wikimedia.org", "reddit.com", "pinterest.com",
        "tumblr.com", "tiktok.com", "snapchat.com", "medium.com", "quora.com",
        "telegram.org", "discord.com",
        "amazon.com", "media-amazon.com", "images-amazon.com", "ssl-images-amazon.com",
        "ebay.com", "walmart.com", "target.com", "aliexpress.com", "alibaba.com",
        "flipkart.com", "bigbasket.com", "myntra.com", "shopify.com", "ajio.com",
        "jiomart.com", "tata.com", "tatacliq.com", "nykaa.com", "meesho.com",
        "paypal.com", "stripe.com", "visa.com", "mastercard.com", "chase.com",
        "bankofamerica.com", "wellsfargo.com", "hsbc.com", "paytm.com", "phonepe.com",
        "razorpay.com", "hdfcbank.com", "icicibank.com", "sbi.co.in", "axisbank.com",
        "kotak.com", "onlinesbi.sbi",
        "zomato.com", "swiggy.com", "uber.com", "olawebs.com", "olacabs.com", "rapido.link", "cherrycabs.in", "cherrycabs.com", "merucabs.com",
        "netflix.com", "twitch.tv", "hulu.com", "disneyplus.com", "spotify.com",
        "vimeo.com", "hotstar.com", "jiocinema.com", "primevideo.com", "bookmyshow.com", "example.com",
        "jio.com", "airtel.in",
        "irctc.co.in", "uidai.gov.in", "epfindia.gov.in", "incometax.gov.in", "mca.gov.in",
        "passportindia.gov.in",
        "researchgate.net", "sciencedirect.com", "springer.com", "ieee.org", "nature.com",
        "academia.edu", "tcs.com", "tcsapps.com"
    }

    local_path = Path(__file__).resolve().parent / "data" / "top_1000_domains.txt"
    if local_path.exists():
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                loaded = {line.strip().lower() for line in f if line.strip()}
                if loaded:
                    return loaded.union(base_trusted)
        except Exception:
            pass

    # Try downloading
    try:
        import urllib.request
        url = "https://gist.githubusercontent.com/jgamblin/62fadd8aa321f7f6a482912a6a317ea3/raw/urls.txt"
        with urllib.request.urlopen(url, timeout=5) as response:
            content = response.read().decode('utf-8')
            downloaded = {line.strip().lower() for line in content.splitlines() if line.strip()}
            if downloaded:
                # Cache to local file
                local_path.parent.mkdir(parents=True, exist_ok=True)
                with open(local_path, "w", encoding="utf-8") as f:
                    for d in sorted(downloaded):
                        f.write(f"{d}\n")
                return downloaded.union(base_trusted)
    except Exception:
        pass

    return base_trusted


TRUSTED_DOMAINS = load_trusted_domains()
TRUSTED_SUFFIXES = tuple("." + td for td in TRUSTED_DOMAINS)


def is_whitelisted(url: str) -> bool:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False

    # Check exact match or subdomain suffix match
    if host in TRUSTED_DOMAINS:
        return True
    if host.endswith(TRUSTED_SUFFIXES):
        return True
    return False


def check_google_safe_browsing(url: str) -> dict | None:
    import os
    import urllib.request
    import json

    api_key = os.getenv("SAFE_BROWSING_API_KEY")
    if not api_key:
        return None

    api_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}"
    payload = {
        "client": {
            "clientId": "url-safety-detection-system",
            "clientVersion": "1.0.0"
        },
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIAL_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}]
        }
    }

    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            if res_data and 'matches' in res_data:
                matches = res_data['matches']
                threat_types = [m.get('threatType', 'UNKNOWN').replace('_', ' ').title() for m in matches]
                feature_vals = extract_url_features(url)
                return {
                    "prediction": "Malicious",
                    "confidence": 100.0,
                    "malicious_probability": 100.0,
                    "risk_level": "High",
                    "reasons": [f"Flagged by Google Safe Browsing: {', '.join(threat_types)}"],
                    "feature_values": {k: float(v) for k, v in feature_vals.items()},
                    "url": url,
                    "explanation": f"Flagged by Google Safe Browsing: {', '.join(threat_types)}"
                }
    except Exception:
        # Ignore errors and fall back to ML model
        pass
    return None


def check_typosquatting(host: str) -> str | None:
    host = host.lower().strip()
    if not host:
        return None

    # If it is exactly in trusted domains or is a subdomain of a trusted domain, it's not a typosquat
    if host in TRUSTED_DOMAINS:
        return None
    for domain in TRUSTED_DOMAINS:
        if host.endswith("." + domain):
            return None

    # Helper function to get SLD (Second Level Domain)
    def get_sld(hostname: str) -> str:
        parts = hostname.split('.')
        if len(parts) >= 2:
            return parts[-2]
        return hostname

    # Helper to calculate edit distance (Levenshtein distance)
    def edit_distance(s1: str, s2: str) -> int:
        if len(s1) > len(s2):
            s1, s2 = s2, s1
        distances = range(len(s1) + 1)
        for i2, c2 in enumerate(s2):
            distances_ = [i2 + 1]
            for i1, c1 in enumerate(s1):
                if c1 == c2:
                    distances_.append(distances[i1])
                else:
                    distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
            distances = distances_
        return distances[-1]

    host_sld = get_sld(host)
    for domain in TRUSTED_DOMAINS:
        domain_sld = get_sld(domain)
        # If SLD is exactly the same, but the domain differs (meaning different TLD, e.g. google.net vs google.com)
        if host_sld == domain_sld:
            return domain
        
        # Calculate edit distance between the SLDs
        dist = edit_distance(host_sld, domain_sld)
        if dist == 1 and len(domain_sld) >= 4:
            return domain
        if dist == 2 and len(domain_sld) >= 6:
            return domain

    return None


def clean_url_for_lookup(u: str) -> str:
    u = u.strip().lower()
    if "://" in u:
        u = u.split("://", 1)[1]
    if u.startswith("www."):
        u = u[4:]
    if u.endswith("/"):
        u = u[:-1]
    return u


def is_host_trusted(host: str) -> bool:
    host = host.lower().strip()
    if not host:
        return False
    if host in TRUSTED_DOMAINS:
        return True
    if host.endswith(TRUSTED_SUFFIXES):
        return True
    return False


def load_known_phishing_urls() -> set[str]:
    phishing_set = set()
    paths = [
        Path(__file__).resolve().parent / "data" / "phishing_simple (1).csv",
        Path(__file__).resolve().parent / "dataset for url" / "phishing_simple (1).csv"
    ]
    for path in paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        parts = line.strip().split(',')
                        if len(parts) >= 3:
                            raw_url = parts[0].strip().lower()
                            domain = parts[1].strip().lower()
                            label = parts[2].strip()
                            if label == '1':
                                if raw_url:
                                    phishing_set.add(clean_url_for_lookup(raw_url))
                                if domain:
                                    phishing_set.add(clean_url_for_lookup(domain))
            except Exception:
                pass
            break
    return phishing_set



KNOWN_PHISHING_URLS = load_known_phishing_urls()


def scan_url(url: str, user_id: int | None = None, store: bool = False) -> dict:
    if not MODEL_PATH.exists():
        raise FileNotFoundError("Trained model not found. Run `python train.py` first.")

    normalized = normalize_url(url)

    from urllib.parse import urlparse
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower()

    # 1. Typosquatting Check
    typo_target = check_typosquatting(host)
    if typo_target:
        feature_vals = extract_url_features(normalized)
        result = {
            "prediction": "Malicious",
            "confidence": 100.0,
            "malicious_probability": 100.0,
            "risk_level": "High",
            "reasons": [f"Typosquatting/Spelling mimicry of trusted domain '{typo_target}'"],
            "feature_values": {k: float(v) for k, v in feature_vals.items()},
            "url": normalized,
            "explanation": f"Typosquatting/Spelling mimicry of trusted domain '{typo_target}'"
        }
    # 2. Whitelist Check
    elif is_whitelisted(normalized):
        feature_vals = extract_url_features(normalized)
        result = {
            "prediction": "Safe",
            "confidence": 100.0,
            "malicious_probability": 0.0,
            "risk_level": "Low",
            "reasons": ["Verified trusted domain (Whitelist)"],
            "feature_values": {k: float(v) for k, v in feature_vals.items()},
            "url": normalized,
            "explanation": "Verified trusted domain (Whitelist)"
        }
    # 3. Blacklist lookup check
    else:
        clean_input = clean_url_for_lookup(url)
        clean_host = clean_url_for_lookup(host)
        if clean_input in KNOWN_PHISHING_URLS or clean_host in KNOWN_PHISHING_URLS:
            feature_vals = extract_url_features(normalized)
            result = {
                "prediction": "Malicious",
                "confidence": 100.0,
                "malicious_probability": 100.0,
                "risk_level": "High",
                "reasons": ["Flagged as malicious in the system database (phishing_simple dataset)"],
                "feature_values": {k: float(v) for k, v in feature_vals.items()},
                "url": normalized,
                "explanation": "Flagged as malicious in the system database (phishing_simple dataset)"
            }
        else:
            # Check if the domain itself is safe
            from urllib.parse import urlparse
            parsed = urlparse(normalized)
            scheme = parsed.scheme or "http"
            netloc = parsed.netloc
            domain_url = f"{scheme}://{netloc}"

            domain_is_safe = False
            domain_result = None

            if domain_url != normalized:
                if is_whitelisted(domain_url):
                    domain_is_safe = True
                else:
                    try:
                        gsb_domain = check_google_safe_browsing(domain_url)
                        if gsb_domain:
                            domain_result = gsb_domain
                        else:
                            domain_result = explain_url(domain_url)
                        
                        if domain_result.get("prediction") == "Safe":
                            domain_is_safe = True
                    except Exception:
                        pass

            if domain_is_safe:
                feature_vals = extract_url_features(normalized)
                result = {
                    "prediction": "Safe",
                    "confidence": domain_result["confidence"] if domain_result else 99.0,
                    "malicious_probability": domain_result["malicious_probability"] if domain_result else 0.0,
                    "risk_level": "Low",
                    "reasons": ["Base domain is verified as Safe"],
                    "feature_values": {k: float(v) for k, v in feature_vals.items()},
                    "url": normalized,
                    "explanation": "Base domain is verified as Safe"
                }
            else:
                gsb_result = check_google_safe_browsing(normalized)
                if gsb_result:
                    result = gsb_result
                else:
                    result = explain_url(normalized)
                    result["url"] = normalized
                    result["explanation"] = "; ".join(result["reasons"])

    if store:
        from database import store_scan_result
        try:
            result["scan_history_id"] = store_scan_result(
                user_id=user_id,
                url=normalized,
                prediction=result["prediction"],
                confidence=result["confidence"],
                risk_level=result["risk_level"],
                explanation=result["explanation"],
            )
        except Exception as exc:
            result["storage_error"] = str(exc)
    return result


def format_result(result: dict) -> str:
    reasons = "\n".join(f"✓ {reason}" for reason in result["reasons"])
    return (
        f"Prediction: {result['prediction']}\n\n"
        f"Confidence: {result['confidence']}%\n\n"
        f"Risk Level: {result['risk_level']}\n\n"
        f"Reasons:\n{reasons}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scan a URL with the trained ML model.")
    parser.add_argument("url")
    parser.add_argument("--user-id", type=int, default=None)
    parser.add_argument("--store", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    output = scan_url(args.url, user_id=args.user_id, store=args.store)
    print(json.dumps(output, indent=2) if args.json else format_result(output))

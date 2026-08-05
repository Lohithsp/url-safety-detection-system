# 🛡️ URL Safety Detection System (URLGuard)

An explainable AI-powered URL safety detection system featuring a hybrid scanning pipeline. It classifies web links as **Safe** or **Malicious** in real time and provides explanations of the decision reasons.

---

## 🚀 Hybrid Scanner Architecture

The safety detection system uses a multi-tier defense architecture to verify URLs:

1. **Trusted Whitelist (Tier 1)**: Bypasses the ML scanner for trusted, high-reputation domains (e.g., `google.com`, `chatgpt.com`, `tcsapps.com`, `github.com`).
2. **Google Safe Browsing API (Tier 2)**: Checks the URL against Google's global, real-time threat database of known malware and social engineering sites.
3. **Local Machine Learning Model (Tier 3)**: Falls back to a local **XGBoost** classifier if the URL is not whitelisted and has no known signatures. It extracts 33 lexical and statistical features (like entropy, digit ratio, subdomains, slash count, etc.) to evaluate new/zero-day threat urls.

---

## 🔑 Key Features

- **Explainable AI (XAI)**: Displays confidence scores, risk levels, and specific feature signals for every scanned link.
- **Google Safe Browsing Check**: Optional API check that queries Google's threat feed directly.
- **Lexical Feature Extraction**: Parses entropy, subdomain structure, character ratios, and suspicious keywords.
- **Admin & User System**:
  - Secure registration with 6-digit email OTP verification.
  - Dedicated admin dashboard to approve/reject users, manage accounts, and view safety metrics.
  - Interactive user panel with scan history, saved logs, and clear analytics.
- **Modern Responsive Design**: Premium dark-themed UI featuring clean micro-animations, statistics grids, and interactive scans.

---

## 🛠️ Technology Stack

- **Backend / API**: Python (Flask), MySQL (via SQLAlchemy & `mysql-connector`)
- **Frontend / Client**: HTML5, Vanilla CSS (Glassmorphism design system), JavaScript (ES6)
- **Machine Learning**: Python (`scikit-learn`, `xgboost`, `pandas`, `numpy`, `joblib`)

---

## 📦 Setup & Installation

### Prerequisites
- Python 3.8 or higher
- MySQL / MariaDB (e.g., via XAMPP)
- Google Safe Browsing API Key (Optional)

### 1. Database Setup
1. Create a MySQL database named `url_safety`.
2. Import the schema using `php/setup.sql` or let `server.py` create the tables automatically on start.

### 2. Configuration (`.env`)
Copy `.env.example` to `.env` and fill in the database and email parameters:
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=url_safety

# (Optional) Google Safe Browsing key
SAFE_BROWSING_API_KEY=your_google_safe_browsing_api_key
```

### 3. Run the Project
1. Install Python packages:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the local server:
   ```bash
   python server.py
   ```
3. Open [http://127.0.0.1:8000/index.html](http://127.0.0.1:8000/index.html) in your browser.
---

## 👤 Default Admin Credentials
- **Email**: `youremail@gmail.com` (Placeholder)
- **Password**: `yourpassword` (Placeholder)

> [!IMPORTANT]
> **Action Required**: Please replace these placeholder credentials in your `.env` file (or configurations in [db_config.php](file:///c:/Users/chand/Downloads/url-safety-detection-system-updated/php/db_config.php) and [server.py](file:///c:/Users/chand/Downloads/url-safety-detection-system-updated/server.py)) with your own email address and secure password before running, deploying, or sharing the project.

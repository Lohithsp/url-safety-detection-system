# GCP Cloud Deployment Guide - URL Safety Detection System (URLGuard)

This guide walks you through the step-by-step process of deploying the **URL Safety Detection System** to Google Cloud Platform (GCP).

---

## 🏗️ Architecture Overview

The system runs as a Python Flask app serving local ML models (XGBoost) and static web pages. It communicates with a MySQL database. For a production deployment, we recommend:

1. **Backend & Frontend**: Google Cloud Run (Serverless, Container-based) or Google App Engine (PaaS).
2. **Database**: Google Cloud SQL for MySQL.
3. **Database connection**: Connected securely via a UNIX socket path (`/cloudsql/...`).

---

## 🛠️ Step 1: Initial GCP Setup

### 1. Install Google Cloud SDK (CLI)
Download and install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) on your local machine.

### 2. Log in and Set Your Project
Open your terminal (PowerShell, Command Prompt, or bash) and log in to your GCP account:
```bash
gcloud auth login
```
After logging in, set your active project ID (replace `YOUR_GCP_PROJECT_ID` with your actual GCP project ID):
```bash
gcloud config set project YOUR_GCP_PROJECT_ID
```

### 3. Enable Required APIs
Run the following command to enable the APIs for Cloud Run, Cloud SQL, and resource management:
```bash
gcloud services enable \
    run.googleapis.com \
    sqladmin.googleapis.com \
    sql-component.googleapis.com \
    compute.googleapis.com \
    appengine.googleapis.com
```

---

## 🗄️ Step 2: Provision a Cloud SQL (MySQL) Database

### 1. Create a MySQL Instance
Create a lightweight Cloud SQL instance in your preferred region (e.g., `us-central1`). We will use the smallest tier (`db-f1-micro`) to minimize costs (or keep it in the free tier if applicable):
```bash
gcloud sql instances create url-safety-db \
    --database-version=MYSQL_8_0 \
    --tier=db-f1-micro \
    --region=us-central1
```

### 2. Set the Root Database Password
Set a secure password for the database `root` user:
```bash
gcloud sql users set-password root \
    --instance=url-safety-db \
    --password="YOUR_DB_ROOT_PASSWORD"
```

### 3. Create the Database
Create the `url_safety` database inside your instance:
```bash
gcloud sql databases create url_safety --instance=url-safety-db
```

### 4. Retrieve your Instance Connection Name
Get the unique connection name for your database. You will need this for connecting the app:
```bash
gcloud sql instances describe url-safety-db --format="value(connectionName)"
```
*Note the output format: `project-id:region:instance-name` (e.g. `my-project-123:us-central1:url-safety-db`). This is your **Instance Connection Name**.*

---

## 🚀 Step 3: Deployment Options

Choose **one** of the two deployment methods below:

### Option A: Deploy to Google Cloud Run (Recommended)
Cloud Run builds your app into a Docker container and hosts it on a serverless container environment. It scales down to 0 instances when idle, incurring minimal or no costs.

#### Run the Deployment Command:
Run the following command from the project root directory. Replace the placeholders with your actual credentials and details:
```bash
gcloud run deploy url-safety-app \
    --source . \
    --region us-central1 \
    --allow-unauthenticated \
    --add-cloudsql-instances YOUR_INSTANCE_CONNECTION_NAME \
    --set-env-vars="DB_USER=root,DB_PASSWORD=YOUR_DB_ROOT_PASSWORD,DB_NAME=url_safety,DB_SOCKET=/cloudsql/YOUR_INSTANCE_CONNECTION_NAME,ADMIN_EMAIL=youremail@gmail.com,ADMIN_PASSWORD=yourpassword,MAIL_FROM_EMAIL=youremail@gmail.com,MAIL_FROM_NAME=URL Safety Check,MAIL_APP_PASSWORD=yourpassword,SMTP_HOST=smtp.gmail.com,SMTP_PORT=465,SMTP_USE_SSL=1,SMTP_USE_TLS=0"
```

*Note: The `--add-cloudsql-instances` flag tells Cloud Run to mount the Cloud SQL proxy, enabling the application to access the database via the local socket `/cloudsql/YOUR_INSTANCE_CONNECTION_NAME`.*

---

### Option B: Deploy to Google App Engine Standard
App Engine hosts the application as a standard Platform-as-a-Service (PaaS). It reads deployment instructions from `app.yaml`.

#### 1. Configure `app.yaml`
Open `app.yaml` and update the environment variables:
- Replace `your-gcp-db-password` with your SQL root password.
- Replace `YOUR_GCP_PROJECT_ID:YOUR_GCP_REGION:YOUR_CLOUD_SQL_INSTANCE_ID` in `DB_SOCKET` with your **Instance Connection Name**.
- Ensure the email settings (`MAIL_APP_PASSWORD`, etc.) are correct.

#### 2. Run the App Engine Deployment:
Run this command from the project root:
```bash
gcloud app deploy
```
Follow the prompts to select a region (e.g., `us-central1`) and confirm the deployment.

---

## 🗃️ Step 4: Initializing the Database Tables

The application is programmed to initialize the database tables automatically on launch.
- When the Flask app starts up on GCP, `server.py` executes `init_db()` and `init_mysql_otp_tables()`, creating the `users`, `login_otps`, `registration_otps`, `settings_store`, `login_activity`, and `auth_attempts` tables.
- During database interaction, `database.py` runs `create_tables()`, generating the `scan_history` table.

Therefore, you **do not** need to manually run `init_db_tables.py` or setup SQL files on Cloud SQL. Once the app finishes deploying and starts running, the database tables will be created automatically.

---

## ✉️ Step 5: Email Configuration (SMTP)

The system relies on sending email OTPs for user registrations and logins. 
- The default configuration uses **Gmail SMTP** (`smtp.gmail.com`) on port `465` (SSL) with a Gmail **App Password**.
- If you use Gmail, ensure you have enabled 2-Step Verification and generated an **App Password** for your account. Replace the `MAIL_APP_PASSWORD` environment variable with this 16-character code (with spaces removed).
- If you wish to use a different SMTP provider (e.g., SendGrid, Mailgun) in production, update these variables during deployment:
  - `SMTP_HOST`: The SMTP provider host.
  - `SMTP_PORT`: Port (e.g., `587` for TLS, `465` for SSL).
  - `SMTP_USE_SSL`: `1` (true) or `0` (false).
  - `SMTP_USE_TLS`: `1` (true) or `0` (false).

---

## 🔍 Step 6: Verifying the Live App

1. Once the deployment command completes, the terminal will print a **Service URL** (e.g., `https://url-safety-app-xxxxxx.a.run.app` or `https://your-project.uc.r.appspot.com`).
2. Open this URL in your web browser. You should be redirected to the login screen (`/user/index.html` or `/auth.html`).
3. You can log in using the default Admin credentials:
   - **Email**: `youremail@gmail.com`
   - **Password**: `yourpassword`
4. Register a test user, log in as the Admin to approve them, and verify that URL scans are properly saved in the Cloud SQL database.

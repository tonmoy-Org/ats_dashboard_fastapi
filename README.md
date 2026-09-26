# 🚀 ATS Recovery Pro — Python FastAPI Backend

FastAPI implementation of `ats_dashboard` backend, supporting high-concurrency SQLite operations, license validation, number dispatching, account recovery sync, and cookie vault management.

---

## 🛠 Features Included

- **License & Authentication (`/api_auth.php`, `/api/auth/login`)**:
  - HWID device binding
  - Subscription expiry checks
  - Bcrypt password validation

- **Account Recovery Sync (`/api_sync.php`, `/api/sync`)**:
  - Master Permanent Vault (`accounts`) insertion
  - Active Work Pool (`accounts_trade`) upsert
  - Automatic interim record purge upon completion

- **Target Number Dispatching (`/api_dispatch.php`, `/api/dispatch`)**:
  - Multi-tier carrier & circle filtering
  - High-speed WAL lock-free dispatch
  - Omni-search & pool statistics

- **Accounts & Pool Actions (`/api_v2_accounts.php`, `/api_v2_actions.php`)**:
  - Role-based and user-based trade pool purging
  - Stuck running status resetting

- **Session Cookies Vault (`/api_cookies.php`, `/api/cookies`)**:
  - Netscape and JSON cookie storage and retrieval

---

## 💻 Local Setup & Execution

1. **Navigate to project directory**:
   ```bash
   cd C:\Users\ASUS\.gemini\antigravity-ide\scratch\ats_dashboard_fastapi
   ```

2. **Install Required Packages**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Server**:
   ```bash
   python run.py
   ```
   Or via Uvicorn directly:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Access API Documentation**:
   - Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

---

## 🌐 Deploying to VPS (`23.95.140.149`)

To run this Python FastAPI backend on the VPS using PM2:

```bash
cd /var/www/ats_dashboard_fastapi
pip install -r requirements.txt
pm2 start "uvicorn main:app --host 0.0.0.0 --port 8000" --name "ats-fastapi-backend"
```

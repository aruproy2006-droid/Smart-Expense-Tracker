import os
import sys
import json
import uuid
import hashlib
import urllib.parse
import mimetypes
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

# Ensure backend directory is in path to import database
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import database

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expenses.db")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

# In-memory sessions dictionary
SESSIONS = {} # token -> {"user_id": user_id, "name": name, "expires": datetime}

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16)
    else:
        salt = bytes.fromhex(salt)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ":" + key.hex()

def verify_password(stored_password, provided_password):
    try:
        salt_hex, key_hex = stored_password.split(":")
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
        return key.hex() == key_hex
    except Exception:
        return False

def get_auth_user(headers):
    auth_header = headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header[7:].strip()
    session = SESSIONS.get(token)
    if not session:
        return None
    if datetime.now() > session["expires"]:
        del SESSIONS[token]
        return None
    # Refresh session expiration
    session["expires"] = datetime.now() + timedelta(days=7)
    return session["user_id"]

class ExpenseTrackerHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        # Silence standard HTTP request logging to keep console clean, or keep minimal
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format%args))

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()
        
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def read_json_body(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                return {}
            body = self.rfile.read(content_length).decode('utf-8')
            return json.loads(body)
        except Exception:
            return None

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
        
    def send_error_json(self, message, status=400):
        self.send_json({"status": "error", "message": message}, status)

    def serve_static(self, path):
        if path == "/" or path == "":
            path = "/index.html"
            
        filepath = os.path.join(FRONTEND_DIR, path.lstrip("/"))
        normalized_path = os.path.normpath(filepath)
        
        # Verify filepath stays within FRONTEND_DIR
        if not normalized_path.startswith(FRONTEND_DIR):
            self.send_error(403, "Access Denied")
            return
            
        if os.path.exists(normalized_path) and os.path.isfile(normalized_path):
            content_type, _ = mimetypes.guess_type(normalized_path)
            if not content_type:
                content_type = "application/octet-stream"
            # Ensure correct MIME type for ES modules JS files
            if normalized_path.endswith(".js"):
                content_type = "application/javascript"
            
            try:
                with open(normalized_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Internal Server Error: {str(e)}")
        else:
            # SPA Fallback: Serve index.html if the file doesn't exist
            index_path = os.path.join(FRONTEND_DIR, "index.html")
            if os.path.exists(index_path):
                try:
                    with open(index_path, "rb") as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                except Exception as e:
                    self.send_error(500, f"SPA Fallback Error: {str(e)}")
            else:
                self.send_error(404, "File Not Found")

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        if path.startswith("/api/"):
            self.handle_api_get(path, parsed_url.query)
        else:
            self.serve_static(path)

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        if path.startswith("/api/"):
            self.handle_api_post(path)
        else:
            self.send_error(405, "Method Not Allowed")

    def do_PUT(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        if path.startswith("/api/"):
            self.handle_api_put(path)
        else:
            self.send_error(405, "Method Not Allowed")

    def do_DELETE(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        if path.startswith("/api/"):
            self.handle_api_delete(path)
        else:
            self.send_error(405, "Method Not Allowed")

    def handle_api_get(self, path, query_str):
        # Public paths
        if path == "/api/health":
            self.send_json({"status": "healthy", "time": datetime.now().isoformat()})
            return
            
        user_id = get_auth_user(self.headers)
        if not user_id:
            self.send_error_json("Unauthorized access", 401)
            return

        # Auto-trigger recurring rules logic on any dashboard load / data view
        database.process_recurring_rules(DB_PATH)

        query_params = urllib.parse.parse_qs(query_str)
        
        if path == "/api/dashboard":
            # Default to current month and year
            now = datetime.now()
            month = int(query_params.get("month", [now.month])[0])
            year = int(query_params.get("year", [now.year])[0])
            
            summary = database.get_dashboard_summary(DB_PATH, user_id, month, year)
            self.send_json(summary)
            
        elif path == "/api/expenses":
            filters = {}
            if "category_id" in query_params:
                filters["category_id"] = int(query_params["category_id"][0])
            if "payment_mode" in query_params:
                filters["payment_mode"] = query_params["payment_mode"][0]
            if "start_date" in query_params:
                filters["start_date"] = query_params["start_date"][0]
            if "end_date" in query_params:
                filters["end_date"] = query_params["end_date"][0]
            if "search" in query_params:
                filters["search"] = query_params["search"][0]
                
            expenses = database.get_expenses(DB_PATH, user_id, filters)
            self.send_json(expenses)
            
        elif path == "/api/categories":
            categories = database.get_categories(DB_PATH, user_id)
            self.send_json(categories)
            
        elif path == "/api/budgets":
            now = datetime.now()
            month = int(query_params.get("month", [now.month])[0])
            year = int(query_params.get("year", [now.year])[0])
            
            budgets = database.get_budgets(DB_PATH, user_id, month, year)
            self.send_json(budgets)
            
        elif path == "/api/recurring":
            rules = database.get_recurring_rules(DB_PATH, user_id)
            self.send_json(rules)
            
        elif path == "/api/notifications":
            notifications = database.get_notifications(DB_PATH, user_id)
            self.send_json(notifications)
            
        else:
            self.send_error_json("Endpoint not found", 404)

    def handle_api_post(self, path):
        # Public endpoints
        if path == "/api/signup":
            body = self.read_json_body()
            if not body or not body.get("name") or not body.get("email") or not body.get("password"):
                self.send_error_json("Name, Email and Password are required")
                return
                
            email = body["email"].strip().lower()
            name = body["name"].strip()
            password = body["password"]
            
            # Simple validation
            if len(password) < 6:
                self.send_error_json("Password must be at least 6 characters long")
                return
                
            existing = database.get_user_by_email(DB_PATH, email)
            if existing:
                self.send_error_json("User with this email already exists")
                return
                
            pwd_hash = hash_password(password)
            user_id = database.create_user(DB_PATH, name, email, pwd_hash)
            
            if user_id:
                # Log them in automatically by generating a session token
                token = str(uuid.uuid4())
                SESSIONS[token] = {
                    "user_id": user_id,
                    "name": name,
                    "expires": datetime.now() + timedelta(days=7)
                }
                self.send_json({"status": "success", "token": token, "name": name, "user_id": user_id})
            else:
                self.send_error_json("Failed to create user")
            return
            
        elif path == "/api/login":
            body = self.read_json_body()
            if not body or not body.get("email") or not body.get("password"):
                self.send_error_json("Email and Password are required")
                return
                
            email = body["email"].strip().lower()
            password = body["password"]
            
            user = database.get_user_by_email(DB_PATH, email)
            if not user or not verify_password(user["password_hash"], password):
                self.send_error_json("Invalid email or password", 401)
                return
                
            token = str(uuid.uuid4())
            SESSIONS[token] = {
                "user_id": user["user_id"],
                "name": user["name"],
                "expires": datetime.now() + timedelta(days=7)
            }
            self.send_json({"status": "success", "token": token, "name": user["name"], "user_id": user["user_id"]})
            return

        # Authenticated endpoints
        user_id = get_auth_user(self.headers)
        if not user_id:
            self.send_error_json("Unauthorized access", 401)
            return
            
        body = self.read_json_body()
        if not body:
            self.send_error_json("Invalid JSON body")
            return

        if path == "/api/logout":
            auth_header = self.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[7:].strip()
                if token in SESSIONS:
                    del SESSIONS[token]
            self.send_json({"status": "success"})
            
        elif path == "/api/expenses":
            required = ["category_id", "amount", "payment_mode", "expense_date"]
            if not all(field in body for field in required):
                self.send_error_json(f"Fields {required} are required")
                return
                
            category_id = int(body["category_id"])
            amount = float(body["amount"])
            payment_mode = body["payment_mode"]
            expense_date = body["expense_date"]
            note = body.get("note", "")
            merchant = body.get("merchant", "")
            
            expense_id = database.create_expense(
                DB_PATH, user_id, category_id, amount, payment_mode, note, merchant, expense_date
            )
            
            # Check budgets and generate notifications if limits exceeded
            alerts = database.check_budget_alerts(DB_PATH, user_id, category_id, amount, expense_date)
            
            self.send_json({"status": "success", "expense_id": expense_id, "alerts": alerts})
            
        elif path == "/api/categories":
            if not body.get("name") or not body.get("color_hex"):
                self.send_error_json("Category name and color are required")
                return
                
            name = body["name"].strip()
            icon = body.get("icon", "tag")
            color_hex = body["color_hex"].strip()
            
            cat_id = database.create_category(DB_PATH, user_id, name, icon, color_hex)
            self.send_json({"status": "success", "category_id": cat_id})
            
        elif path == "/api/budgets":
            required = ["category_id", "month", "year", "limit_amount"]
            if not all(field in body for field in required):
                self.send_error_json(f"Fields {required} are required")
                return
                
            category_id = int(body["category_id"])
            month = int(body["month"])
            year = int(body["year"])
            limit_amount = float(body["limit_amount"])
            alert_threshold = int(body.get("alert_threshold_pct", 80))
            
            budget_id = database.set_budget(
                DB_PATH, user_id, category_id, month, year, limit_amount, alert_threshold
            )
            self.send_json({"status": "success", "budget_id": budget_id})
            
        elif path == "/api/recurring":
            required = ["category_id", "amount", "frequency", "next_due_date"]
            if not all(field in body for field in required):
                self.send_error_json(f"Fields {required} are required")
                return
                
            category_id = int(body["category_id"])
            amount = float(body["amount"])
            frequency = body["frequency"] # 'weekly' | 'monthly' | 'yearly'
            next_due_date = body["next_due_date"]
            
            rule_id = database.create_recurring_rule(
                DB_PATH, user_id, category_id, amount, frequency, next_due_date
            )
            self.send_json({"status": "success", "recurring_rule_id": rule_id})
            
        else:
            self.send_error_json("Endpoint not found", 404)

    def handle_api_put(self, path):
        user_id = get_auth_user(self.headers)
        if not user_id:
            self.send_error_json("Unauthorized access", 401)
            return
            
        body = self.read_json_body()
        if not body:
            self.send_error_json("Invalid JSON body")
            return

        if path == "/api/expenses":
            required = ["expense_id", "category_id", "amount", "payment_mode", "expense_date"]
            if not all(field in body for field in required):
                self.send_error_json(f"Fields {required} are required")
                return
                
            expense_id = int(body["expense_id"])
            category_id = int(body["category_id"])
            amount = float(body["amount"])
            payment_mode = body["payment_mode"]
            expense_date = body["expense_date"]
            note = body.get("note", "")
            merchant = body.get("merchant", "")
            
            updated = database.update_expense(
                DB_PATH, expense_id, user_id, category_id, amount, payment_mode, note, merchant, expense_date
            )
            
            if updated:
                alerts = database.check_budget_alerts(DB_PATH, user_id, category_id, amount, expense_date)
                self.send_json({"status": "success", "alerts": alerts})
            else:
                self.send_error_json("Expense not found or update failed")
                
        elif path == "/api/recurring":
            required = ["recurring_rule_id", "amount", "frequency", "next_due_date", "is_active"]
            if not all(field in body for field in required):
                self.send_error_json(f"Fields {required} are required")
                return
                
            rule_id = int(body["recurring_rule_id"])
            amount = float(body["amount"])
            frequency = body["frequency"]
            next_due_date = body["next_due_date"]
            is_active = int(body["is_active"])
            
            updated = database.update_recurring_rule(
                DB_PATH, rule_id, user_id, amount, frequency, next_due_date, is_active
            )
            if updated:
                self.send_json({"status": "success"})
            else:
                self.send_error_json("Recurring rule not found or update failed")
                
        elif path == "/api/notifications":
            if not body.get("notification_id"):
                self.send_error_json("notification_id is required")
                return
                
            notif_id = int(body["notification_id"])
            updated = database.mark_notification_read(DB_PATH, notif_id, user_id)
            if updated:
                self.send_json({"status": "success"})
            else:
                self.send_error_json("Notification not found or update failed")
                
        else:
            self.send_error_json("Endpoint not found", 404)

    def handle_api_delete(self, path):
        user_id = get_auth_user(self.headers)
        if not user_id:
            self.send_error_json("Unauthorized access", 401)
            return
            
        body = self.read_json_body()
        if not body:
            self.send_error_json("Invalid JSON body")
            return

        if path == "/api/expenses":
            if not body.get("expense_id"):
                self.send_error_json("expense_id is required")
                return
            expense_id = int(body["expense_id"])
            deleted = database.delete_expense(DB_PATH, expense_id, user_id)
            if deleted:
                self.send_json({"status": "success"})
            else:
                self.send_error_json("Expense not found or deletion failed")
                
        elif path == "/api/recurring":
            if not body.get("recurring_rule_id"):
                self.send_error_json("recurring_rule_id is required")
                return
            rule_id = int(body["recurring_rule_id"])
            deleted = database.delete_recurring_rule(DB_PATH, rule_id, user_id)
            if deleted:
                self.send_json({"status": "success"})
            else:
                self.send_error_json("Recurring rule not found or deletion failed")
        else:
            self.send_error_json("Endpoint not found", 404)

def run_server(port=8000):
    # Initialize database
    print(f"Initializing SQLite database at: {DB_PATH}...")
    database.init_db(DB_PATH)
    
    server_address = ('', port)
    httpd = HTTPServer(server_address, ExpenseTrackerHandler)
    print(f"Smart Expense Tracker Server running on port {port}...")
    print(f"Local App Address: http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port)

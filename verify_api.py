import urllib.request
import urllib.error
import json
from datetime import datetime

API_BASE = "http://localhost:8000/api"

def make_request(path, method="GET", body=None, token=None):
    url = f"{API_BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    data = None
    if body:
        data = json.dumps(body).encode("utf-8")
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            return json.loads(res_body) if res_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"HTTP Error {e.code} on {method} {path}: {err_body}")
        raise e
    except Exception as e:
        print(f"Connection Error on {method} {path}: {str(e)}")
        raise e

def run_verification():
    print("--- STARTING API VERIFICATION ---")
    
    # 1. Signup a new user
    signup_payload = {
        "name": "Arjun Test",
        "email": f"arjun_{int(datetime.now().timestamp())}@test.com",
        "password": "password123"
    }
    print(f"Registering user: {signup_payload['email']}")
    signup_res = make_request("/signup", "POST", signup_payload)
    assert signup_res.get("status") == "success", "Signup failed"
    token = signup_res.get("token")
    print(f"Signup successful. Received Session Token: {token[:8]}...")
    
    # 2. Get categories and find 'Food'
    print("Fetching seeded categories...")
    categories = make_request("/categories", "GET", token=token)
    assert len(categories) > 0, "No seeded categories found"
    
    food_cat = next((c for c in categories if c["name"] == "Food"), None)
    assert food_cat is not None, "Food category not found"
    food_id = food_cat["category_id"]
    print(f"Found 'Food' category with ID: {food_id}")
    
    # 3. Set a budget limit of $200 for Food in current month
    now = datetime.now()
    budget_payload = {
        "category_id": food_id,
        "month": now.month,
        "year": now.year,
        "limit_amount": 200.0,
        "alert_threshold_pct": 80
    }
    print(f"Setting budget of $200 for Food in month {now.month}/{now.year}")
    budget_res = make_request("/budgets", "POST", budget_payload, token=token)
    assert budget_res.get("status") == "success", "Failed to set budget"
    
    # 4. Log $150 expense (75% of budget)
    expense_1 = {
        "category_id": food_id,
        "amount": 150.0,
        "payment_mode": "upi",
        "expense_date": now.strftime("%Y-%m-%d"),
        "note": "Weekly groceries",
        "merchant": "Supermarket"
    }
    print("Logging expense 1: $150 for groceries...")
    exp1_res = make_request("/expenses", "POST", expense_1, token=token)
    assert exp1_res.get("status") == "success", "Failed to log expense 1"
    assert len(exp1_res.get("alerts", [])) == 0, "Warning triggered unexpectedly at 75%"
    
    # 5. Log $60 expense (makes total $210, which exceeds $200)
    expense_2 = {
        "category_id": food_id,
        "amount": 60.0,
        "payment_mode": "card",
        "expense_date": now.strftime("%Y-%m-%d"),
        "note": "Dinner with friends",
        "merchant": "Spicy Garden"
    }
    print("Logging expense 2: $60 for dinner...")
    exp2_res = make_request("/expenses", "POST", expense_2, token=token)
    assert exp2_res.get("status") == "success", "Failed to log expense 2"
    
    alerts = exp2_res.get("alerts", [])
    print(f"Active Alerts returned from POST: {alerts}")
    assert len(alerts) > 0, "No alerts returned when exceeding budget limit"
    assert any(a["type"] == "budget_exceeded" for a in alerts), "Expected budget_exceeded alert type"
    
    # 6. Fetch dashboard summary and verify total spent, budget, remaining
    print("Fetching dashboard summary...")
    dash = make_request("/dashboard", "GET", token=token)
    print(f"Dashboard Stats: Spent={dash['total_spent']}, Budget={dash['total_budget']}, Remaining={dash['total_budget'] - dash['total_spent']}")
    assert dash["total_spent"] == 210.0, f"Expected total spent 210.0, got {dash['total_spent']}"
    assert dash["total_budget"] == 200.0, f"Expected budget 200.0, got {dash['total_budget']}"
    assert len(dash["recent_expenses"]) == 2, f"Expected 2 recent expenses, got {len(dash['recent_expenses'])}"
    
    # 7. Fetch notifications log
    print("Fetching notifications log...")
    notifications = make_request("/notifications", "GET", token=token)
    print(f"Total Notifications logged: {len(notifications)}")
    assert len(notifications) > 0, "No notifications logged in db"
    print(f"Latest Notification Message: {notifications[0]['message']}")
    
    print("--- API VERIFICATION COMPLETED SUCCESSFULLY ---")

if __name__ == "__main__":
    run_verification()

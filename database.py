import sqlite3
import os
from datetime import datetime

DEFAULT_CATEGORIES = [
    {"name": "Food", "icon": "utensils", "color_hex": "#ef4444"},        # Red
    {"name": "Travel", "icon": "car", "color_hex": "#3b82f6"},           # Blue
    {"name": "Bills", "icon": "file-invoice-dollar", "color_hex": "#eab308"}, # Yellow
    {"name": "Shopping", "icon": "shopping-bag", "color_hex": "#a855f7"},  # Purple
    {"name": "Entertainment", "icon": "film", "color_hex": "#ec4899"},   # Pink
    {"name": "Other", "icon": "tag", "color_hex": "#6b7280"}             # Gray
]

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        auth_provider TEXT DEFAULT 'email',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, -- NULL = system default
        name TEXT NOT NULL,
        icon TEXT,
        color_hex TEXT,
        is_default INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        payment_mode TEXT NOT NULL, -- 'cash' | 'upi' | 'card' | 'wallet' | 'other'
        note TEXT,
        merchant TEXT,
        expense_date TEXT NOT NULL, -- YYYY-MM-DD
        is_recurring INTEGER DEFAULT 0,
        recurring_rule_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (category_id) REFERENCES categories(category_id),
        FOREIGN KEY (recurring_rule_id) REFERENCES recurring_rules(recurring_rule_id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recurring_rules (
        recurring_rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        frequency TEXT NOT NULL, -- 'monthly' | 'weekly' | 'yearly'
        next_due_date TEXT NOT NULL, -- YYYY-MM-DD
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (category_id) REFERENCES categories(category_id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category_id INTEGER NOT NULL,
        month INTEGER NOT NULL, -- 1-12
        year INTEGER NOT NULL,
        limit_amount REAL NOT NULL,
        alert_threshold_pct INTEGER DEFAULT 80,
        UNIQUE(user_id, category_id, month, year),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (category_id) REFERENCES categories(category_id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT, -- 'budget_warning' | 'budget_exceeded' | 'recurring_due'
        message TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    """)
    
    # Indexes for speed
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, expense_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id);")
    
    # Seed default categories if empty
    cursor.execute("SELECT COUNT(*) FROM categories WHERE user_id IS NULL")
    if cursor.fetchone()[0] == 0:
        for cat in DEFAULT_CATEGORIES:
            cursor.execute(
                "INSERT INTO categories (user_id, name, icon, color_hex, is_default) VALUES (NULL, ?, ?, ?, 1)",
                (cat["name"], cat["icon"], cat["color_hex"])
            )
            
    conn.commit()
    conn.close()

# User operations
def create_user(db_path, name, email, password_hash):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_email(db_path, email):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_id(db_path, user_id):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# Category operations
def get_categories(db_path, user_id):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM categories WHERE user_id IS NULL OR user_id = ? ORDER BY is_default DESC, name ASC",
        (user_id,)
    )
    categories = cursor.fetchall()
    conn.close()
    return [dict(cat) for cat in categories]

def create_category(db_path, user_id, name, icon, color_hex):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO categories (user_id, name, icon, color_hex, is_default) VALUES (?, ?, ?, ?, 0)",
        (user_id, name, icon, color_hex)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

# Expense operations
def create_expense(db_path, user_id, category_id, amount, payment_mode, note, merchant, expense_date, is_recurring=0, recurring_rule_id=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO expenses (user_id, category_id, amount, payment_mode, note, merchant, expense_date, is_recurring, recurring_rule_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, category_id, amount, payment_mode, note, merchant, expense_date, is_recurring, recurring_rule_id)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def update_expense(db_path, expense_id, user_id, category_id, amount, payment_mode, note, merchant, expense_date):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE expenses 
           SET category_id = ?, amount = ?, payment_mode = ?, note = ?, merchant = ?, expense_date = ?
           WHERE expense_id = ? AND user_id = ?""",
        (category_id, amount, payment_mode, note, merchant, expense_date, expense_id, user_id)
    )
    conn.commit()
    changes = conn.changes()
    conn.close()
    return changes > 0

def delete_expense(db_path, expense_id, user_id):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE expense_id = ? AND user_id = ?", (expense_id, user_id))
    conn.commit()
    changes = conn.changes()
    conn.close()
    return changes > 0

def get_expenses(db_path, user_id, filters=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    query = """
        SELECT e.*, c.name as category_name, c.icon as category_icon, c.color_hex as category_color 
        FROM expenses e
        JOIN categories c ON e.category_id = c.category_id
        WHERE e.user_id = ?
    """
    params = [user_id]
    
    if filters:
        if filters.get("category_id"):
            query += " AND e.category_id = ?"
            params.append(filters["category_id"])
        if filters.get("payment_mode"):
            query += " AND e.payment_mode = ?"
            params.append(filters["payment_mode"])
        if filters.get("start_date"):
            query += " AND e.expense_date >= ?"
            params.append(filters["start_date"])
        if filters.get("end_date"):
            query += " AND e.expense_date <= ?"
            params.append(filters["end_date"])
        if filters.get("search"):
            query += " AND (e.note LIKE ? OR e.merchant LIKE ?)"
            search_param = f"%{filters['search']}%"
            params.append(search_param)
            params.append(search_param)
            
    query += " ORDER BY e.expense_date DESC, e.expense_id DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Budget operations
def get_budgets(db_path, user_id, month, year):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT b.*, c.name as category_name, c.icon as category_icon, c.color_hex as category_color
           FROM budgets b
           JOIN categories c ON b.category_id = c.category_id
           WHERE b.user_id = ? AND b.month = ? AND b.year = ?""",
        (user_id, month, year)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def set_budget(db_path, user_id, category_id, month, year, limit_amount, alert_threshold_pct=80):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO budgets (user_id, category_id, month, year, limit_amount, alert_threshold_pct)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(user_id, category_id, month, year) 
           DO UPDATE SET limit_amount = EXCLUDED.limit_amount, alert_threshold_pct = EXCLUDED.alert_threshold_pct""",
        (user_id, category_id, month, year, limit_amount, alert_threshold_pct)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

# Check budget alert conditions and insert warning notifications if needed
def check_budget_alerts(db_path, user_id, category_id, amount, date_str):
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        month = date_obj.month
        year = date_obj.year
    except ValueError:
        return []

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # 1. Fetch budget for this category, user, and month/year
    cursor.execute(
        "SELECT limit_amount, alert_threshold_pct FROM budgets WHERE user_id = ? AND category_id = ? AND month = ? AND year = ?",
        (user_id, category_id, month, year)
    )
    budget = cursor.fetchone()
    if not budget:
        conn.close()
        return []
        
    limit_amount = budget["limit_amount"]
    threshold_pct = budget["alert_threshold_pct"]
    
    # 2. Fetch category details
    cursor.execute("SELECT name FROM categories WHERE category_id = ?", (category_id,))
    category_row = cursor.fetchone()
    category_name = category_row["name"] if category_row else "Unknown"

    # 3. Calculate total spend this month in this category
    cursor.execute(
        """SELECT SUM(amount) FROM expenses 
           WHERE user_id = ? AND category_id = ? 
             AND strftime('%m', expense_date) = ? 
             AND strftime('%Y', expense_date) = ?""",
        (user_id, category_id, f"{month:02d}", f"{year:4d}")
    )
    current_spend = cursor.fetchone()[0] or 0.0
    
    alerts_created = []
    
    # 4. Check if crossed limits
    if current_spend >= limit_amount:
        # Check if we already sent 100% notification this month
        cursor.execute(
            """SELECT COUNT(*) FROM notifications 
               WHERE user_id = ? AND type = 'budget_exceeded' 
                 AND message LIKE ? AND strftime('%m', created_at) = ? AND strftime('%Y', created_at) = ?""",
            (user_id, f"%{category_name}%", f"{month:02d}", f"{year:4d}")
        )
        if cursor.fetchone()[0] == 0:
            msg = f"Alert: You have exceeded your monthly budget limit of ${limit_amount:.2f} for '{category_name}'. Current spending is ${current_spend:.2f}."
            cursor.execute(
                "INSERT INTO notifications (user_id, type, message) VALUES (?, 'budget_exceeded', ?)",
                (user_id, msg)
            )
            alerts_created.append({"type": "budget_exceeded", "message": msg})
            
    elif current_spend >= (limit_amount * (threshold_pct / 100.0)):
        # Check if we already sent warning or exceeded notification this month
        cursor.execute(
            """SELECT COUNT(*) FROM notifications 
               WHERE user_id = ? AND (type = 'budget_warning' OR type = 'budget_exceeded') 
                 AND message LIKE ? AND strftime('%m', created_at) = ? AND strftime('%Y', created_at) = ?""",
            (user_id, f"%{category_name}%", f"{month:02d}", f"{year:4d}")
        )
        if cursor.fetchone()[0] == 0:
            msg = f"Warning: You have used {threshold_pct}% of your monthly budget for '{category_name}'. Current spending is ${current_spend:.2f} of ${limit_amount:.2f}."
            cursor.execute(
                "INSERT INTO notifications (user_id, type, message) VALUES (?, 'budget_warning', ?)",
                (user_id, msg)
            )
            alerts_created.append({"type": "budget_warning", "message": msg})
            
    conn.commit()
    conn.close()
    return alerts_created

# Recurring expense rule operations
def get_recurring_rules(db_path, user_id):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT r.*, c.name as category_name, c.icon as category_icon, c.color_hex as category_color
           FROM recurring_rules r
           JOIN categories c ON r.category_id = c.category_id
           WHERE r.user_id = ?""",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def create_recurring_rule(db_path, user_id, category_id, amount, frequency, next_due_date):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO recurring_rules (user_id, category_id, amount, frequency, next_due_date, is_active)
           VALUES (?, ?, ?, ?, ?, 1)""",
        (user_id, category_id, amount, frequency, next_due_date)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def update_recurring_rule(db_path, rule_id, user_id, amount, frequency, next_due_date, is_active):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE recurring_rules 
           SET amount = ?, frequency = ?, next_due_date = ?, is_active = ?
           WHERE recurring_rule_id = ? AND user_id = ?""",
        (amount, frequency, next_due_date, is_active, rule_id, user_id)
    )
    conn.commit()
    changes = conn.changes()
    conn.close()
    return changes > 0

def delete_recurring_rule(db_path, rule_id, user_id):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recurring_rules WHERE recurring_rule_id = ? AND user_id = ?", (rule_id, user_id))
    conn.commit()
    changes = conn.changes()
    conn.close()
    return changes > 0

# Notifications operations
def get_notifications(db_path, user_id):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def mark_notification_read(db_path, notification_id, user_id):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE notifications SET is_read = 1 WHERE notification_id = ? AND user_id = ?",
        (notification_id, user_id)
    )
    conn.commit()
    changes = conn.changes()
    conn.close()
    return changes > 0

# Dashboard Aggregations
def get_dashboard_summary(db_path, user_id, month, year):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Format month as 02d
    month_str = f"{month:02d}"
    year_str = f"{year:4d}"
    
    # 1. Total spent this month
    cursor.execute(
        """SELECT SUM(amount) FROM expenses 
           WHERE user_id = ? 
             AND strftime('%m', expense_date) = ? 
             AND strftime('%Y', expense_date) = ?""",
        (user_id, month_str, year_str)
    )
    total_spent = cursor.fetchone()[0] or 0.0
    
    # 2. Total budget limits for this month
    cursor.execute(
        "SELECT SUM(limit_amount) FROM budgets WHERE user_id = ? AND month = ? AND year = ?",
        (user_id, month, year)
    )
    total_budget = cursor.fetchone()[0] or 0.0
    
    # 3. Category-wise breakdown (actual spend vs limit)
    cursor.execute(
        """SELECT c.category_id, c.name, c.icon, c.color_hex,
                  COALESCE(b.limit_amount, 0) as limit_amount,
                  (SELECT SUM(e.amount) FROM expenses e 
                   WHERE e.user_id = ? AND e.category_id = c.category_id
                     AND strftime('%m', e.expense_date) = ? 
                     AND strftime('%Y', e.expense_date) = ?) as actual_spend
           FROM categories c
           LEFT JOIN budgets b ON c.category_id = b.category_id 
             AND b.user_id = ? AND b.month = ? AND b.year = ?
           WHERE c.user_id IS NULL OR c.user_id = ?""",
        (user_id, month_str, year_str, user_id, month, year, user_id)
    )
    categories_raw = cursor.fetchall()
    category_breakdown = []
    for cat in categories_raw:
        spend = cat["actual_spend"] or 0.0
        # Only include if there is a budget or actual spending
        if cat["limit_amount"] > 0 or spend > 0:
            category_breakdown.append({
                "category_id": cat["category_id"],
                "name": cat["name"],
                "icon": cat["icon"],
                "color_hex": cat["color_hex"],
                "limit_amount": cat["limit_amount"],
                "actual_spend": spend
            })
            
    # 4. Daily spend trend for this month
    # Return days 1 to current/last day of month with total spend
    cursor.execute(
        """SELECT strftime('%d', expense_date) as day, SUM(amount) as daily_sum 
           FROM expenses 
           WHERE user_id = ? 
             AND strftime('%m', expense_date) = ? 
             AND strftime('%Y', expense_date) = ?
           GROUP BY day
           ORDER BY day ASC""",
        (user_id, month_str, year_str)
    )
    trend_rows = cursor.fetchall()
    trend_map = {int(row["day"]): row["daily_sum"] for row in trend_rows}
    
    # Build list for trend chart
    import calendar
    _, num_days = calendar.monthrange(year, month)
    
    # Let's adjust num_days to not go beyond today if it's the current month/year
    today = datetime.now()
    max_day = num_days
    if today.year == year and today.month == month:
        max_day = today.day
        
    trend_data = []
    running_total = 0.0
    for d in range(1, max_day + 1):
        day_spend = trend_map.get(d, 0.0)
        running_total += day_spend
        trend_data.append({
            "day": d,
            "amount": day_spend,
            "cumulative": running_total
        })
        
    # 5. Recent expenses (latest 5)
    cursor.execute(
        """SELECT e.*, c.name as category_name, c.icon as category_icon, c.color_hex as category_color 
           FROM expenses e
           JOIN categories c ON e.category_id = c.category_id
           WHERE e.user_id = ?
           ORDER BY e.expense_date DESC, e.expense_id DESC
           LIMIT 5""",
        (user_id,)
    )
    recent_expenses = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "total_spent": total_spent,
        "total_budget": total_budget,
        "category_breakdown": category_breakdown,
        "trend_data": trend_data,
        "recent_expenses": recent_expenses
    }

# Process recurring expenses whose due dates have passed
def process_recurring_rules(db_path):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Fetch all active rules that are due
    cursor.execute(
        "SELECT * FROM recurring_rules WHERE is_active = 1 AND next_due_date <= ?",
        (today_str,)
    )
    due_rules = cursor.fetchall()
    
    logs_created = []
    
    for rule in due_rules:
        # Create expense
        cursor.execute(
            """INSERT INTO expenses (user_id, category_id, amount, payment_mode, note, merchant, expense_date, is_recurring, recurring_rule_id)
               VALUES (?, ?, ?, 'other', ?, ?, ?, 1, ?)""",
            (rule["user_id"], rule["category_id"], rule["amount"], f"Recurring: {rule['frequency']}", "System Auto", rule["next_due_date"], rule["recurring_rule_id"])
        )
        expense_id = cursor.lastrowid
        
        # Calculate next due date
        from datetime import timedelta
        due_date = datetime.strptime(rule["next_due_date"], "%Y-%m-%d")
        
        if rule["frequency"] == "weekly":
            next_due = due_date + timedelta(days=7)
        elif rule["frequency"] == "monthly":
            # Add a month
            # Basic month addition logic
            import calendar
            month = due_date.month
            year = due_date.year
            month += 1
            if month > 12:
                month = 1
                year += 1
            _, max_days = calendar.monthrange(year, month)
            day = min(due_date.day, max_days)
            next_due = datetime(year, month, day)
        elif rule["frequency"] == "yearly":
            # Add a year
            year = due_date.year + 1
            # leap year adjustment
            day = due_date.day
            if due_date.month == 2 and due_date.day == 29:
                import calendar
                if not calendar.isleap(year):
                    day = 28
            next_due = datetime(year, due_date.month, day)
        else:
            next_due = due_date + timedelta(days=30) # default
            
        next_due_str = next_due.strftime("%Y-%m-%d")
        
        # Update rule's next due date
        cursor.execute(
            "UPDATE recurring_rules SET next_due_date = ? WHERE recurring_rule_id = ?",
            (next_due_str, rule["recurring_rule_id"])
        )
        
        # Create alert/notification
        cursor.execute(
            "SELECT name FROM categories WHERE category_id = ?",
            (rule["category_id"],)
        )
        cat_row = cursor.fetchone()
        cat_name = cat_row["name"] if cat_row else "Unknown"
        
        msg = f"Auto-Logged recurring expense of ${rule['amount']:.2f} for '{cat_name}' (due on {rule['next_due_date']})."
        cursor.execute(
            "INSERT INTO notifications (user_id, type, message) VALUES (?, 'recurring_due', ?)",
            (rule["user_id"], msg)
        )
        
        logs_created.append({
            "user_id": rule["user_id"],
            "category_id": rule["category_id"],
            "amount": rule["amount"],
            "expense_id": expense_id,
            "next_due_date": next_due_str
        })
        
    conn.commit()
    conn.close()
    return logs_created

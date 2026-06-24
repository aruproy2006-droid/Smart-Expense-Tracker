// DASHBOARD VIEW COMPONENT
import { fetchAPI } from '../api.js';
import { state, openModal, closeAllModals, loadNotifications } from '../app.js';

let categoryChartInstance = null;
let trendChartInstance = null;

export async function renderDashboard() {
    setupDashboardListeners();
    await loadDashboardData();
}

async function loadDashboardData() {
    try {
        const summary = await fetchAPI(`/dashboard?month=${state.currentMonth}&year=${state.currentYear}`);
        
        // 1. Render upper metric figures
        document.getElementById('dash-spent-val').textContent = `$${summary.total_spent.toFixed(2)}`;
        document.getElementById('dash-budget-val').textContent = `$${summary.total_budget.toFixed(2)}`;
        
        const remaining = summary.total_budget - summary.total_spent;
        const remValEl = document.getElementById('dash-rem-val');
        remValEl.textContent = `$${remaining.toFixed(2)}`;
        
        // Dynamic remaining balance color
        if (remaining < 0) {
            remValEl.style.color = 'var(--color-danger)';
            document.getElementById('dash-rem-sub').textContent = 'Over budget limit';
        } else if (remaining < (summary.total_budget * 0.2)) {
            remValEl.style.color = 'var(--color-warning)';
            document.getElementById('dash-rem-sub').textContent = 'Approaching limit';
        } else {
            remValEl.style.color = 'var(--color-success)';
            document.getElementById('dash-rem-sub').textContent = 'Safe to spend';
        }
        
        // 2. Render Recent Expenses
        renderRecentExpenses(summary.recent_expenses);
        
        // 3. Render Budget Limit bars
        renderBudgetProgress(summary.category_breakdown);
        
        // 4. Render Analytics Charts
        renderTrendChart(summary.trend_data);
        renderCategoryChart(summary.category_breakdown);
        
    } catch (err) {
        console.error('Failed to load dashboard summary:', err);
    }
}

function renderRecentExpenses(expenses) {
    const tbody = document.getElementById('dash-recent-expenses-tbody');
    if (expenses.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">No recent expenses. Tap Quick Add to start!</td></tr>`;
        return;
    }
    
    tbody.innerHTML = expenses.map(e => {
        const dateObj = new Date(e.expense_date);
        const formattedDate = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        const name = e.merchant ? `${e.merchant} — ${e.note}` : (e.note || 'Expense');
        
        return `
            <tr>
                <td>
                    <div style="font-weight:600;">${e.merchant || 'None'}</div>
                    <div style="font-size:0.78rem;" class="text-muted">${e.note || 'No description'}</div>
                </td>
                <td>
                    <span class="category-indicator" style="background-color: ${e.category_color}1a; color: ${e.category_color};">
                        <span class="category-icon-circle" style="background-color: ${e.category_color};">
                            <i data-lucide="${e.category_icon}"></i>
                        </span>
                        ${e.category_name}
                    </span>
                </td>
                <td><span class="payment-mode-tag">${e.payment_mode}</span></td>
                <td style="font-size: 0.85rem;" class="text-muted">${formattedDate}</td>
                <td class="text-right" style="font-weight:600; color:var(--text-primary);">$${e.amount.toFixed(2)}</td>
                <td class="text-center">
                    <button class="table-action-btn delete-action dash-delete-expense-btn" data-expense-id="${e.expense_id}" title="Delete">
                        <i data-lucide="trash-2" style="width:16px;height:16px;"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
    
    // Bind deletes
    tbody.querySelectorAll('.dash-delete-expense-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const expenseId = btn.getAttribute('data-expense-id');
            if (confirm('Are you sure you want to delete this expense?')) {
                try {
                    await fetchAPI('/expenses', {
                        method: 'DELETE',
                        body: JSON.stringify({ expense_id: expenseId })
                    });
                    loadDashboardData();
                    loadNotifications(); // Reload notifications count/alerts
                } catch (err) {
                    alert('Failed to delete expense: ' + err.message);
                }
            }
        });
    });
    
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

function renderBudgetProgress(breakdown) {
    const container = document.getElementById('dash-budget-bars-container');
    const budgetsOnly = breakdown.filter(cat => cat.limit_amount > 0);
    
    if (budgetsOnly.length === 0) {
        container.innerHTML = `<div class="empty-budgets text-center text-muted py-4">No category budgets set for this month.</div>`;
        return;
    }
    
    container.innerHTML = budgetsOnly.map(b => {
        const pct = b.limit_amount > 0 ? (b.actual_spend / b.limit_amount) * 100 : 0;
        let fillClass = 'fill-safe';
        if (pct >= 100) fillClass = 'fill-danger';
        else if (pct >= 80) fillClass = 'fill-warning';
        
        return `
            <div class="budget-bar-item">
                <div class="budget-bar-info flex-between">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span class="category-icon-circle" style="background-color: ${b.color_hex}; width:16px; height:16px; border-radius:50%;">
                            <i data-lucide="${b.icon}" style="width:8px; height:8px; color:white;"></i>
                        </span>
                        <span style="font-weight:500;">${b.name}</span>
                    </div>
                    <span class="text-muted" style="font-size:0.82rem;">
                        <strong style="color:var(--text-primary); font-weight:600;">$${b.actual_spend.toFixed(0)}</strong> of $${b.limit_amount.toFixed(0)} (${pct.toFixed(0)}%)
                    </span>
                </div>
                <div class="budget-bar-track">
                    <div class="budget-bar-fill ${fillClass}" style="width: ${Math.min(pct, 100)}%;"></div>
                </div>
            </div>
        `;
    }).join('');
    
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

// CHART INTEGRATION
function renderTrendChart(trendData) {
    const ctx = document.getElementById('trend-chart').getContext('2d');
    
    if (trendChartInstance) {
        trendChartInstance.destroy();
    }
    
    const labels = trendData.map(d => `Day ${d.day}`);
    const dailyData = trendData.map(d => d.amount);
    const cumulativeData = trendData.map(d => d.cumulative);
    
    trendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Cumulative Spent',
                    data: cumulativeData,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.08)',
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2.5,
                    pointRadius: 2,
                    pointHoverRadius: 6,
                },
                {
                    label: 'Daily Spending',
                    data: dailyData,
                    borderColor: 'rgba(6, 182, 212, 0.4)',
                    backgroundColor: 'rgba(6, 182, 212, 0.8)',
                    type: 'bar',
                    barThickness: 6,
                    borderRadius: 3,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#9ca3af',
                        font: { family: 'Inter', size: 11 }
                    }
                },
                tooltip: {
                    backgroundColor: '#1e2638',
                    titleColor: '#f3f4f6',
                    bodyColor: '#e5e7eb',
                    borderColor: 'rgba(255,255,255,0.08)',
                    borderWidth: 1,
                    padding: 12,
                    font: { family: 'Inter' }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.02)' },
                    ticks: { color: '#6b7280', font: { family: 'Inter', size: 10 } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                    ticks: { color: '#6b7280', font: { family: 'Inter', size: 10 } }
                }
            }
        }
    });
}

function renderCategoryChart(breakdown) {
    const ctx = document.getElementById('category-chart').getContext('2d');
    
    if (categoryChartInstance) {
        categoryChartInstance.destroy();
    }
    
    // Filter out categories with zero spending
    const activeData = breakdown.filter(cat => cat.actual_spend > 0);
    
    if (activeData.length === 0) {
        // Draw empty state chart message
        ctx.clearRect(0, 0, 300, 300);
        ctx.fillStyle = "#6b7280";
        ctx.font = "13px Inter";
        ctx.textAlign = "center";
        ctx.fillText("No spending data to display chart", 150, 150);
        return;
    }
    
    const labels = activeData.map(d => d.name);
    const dataVals = activeData.map(d => d.actual_spend);
    const bgColors = activeData.map(d => d.color_hex);
    
    categoryChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: dataVals,
                backgroundColor: bgColors,
                borderWidth: 2,
                borderColor: '#131a26',
                hoverOffset: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#9ca3af',
                        boxWidth: 10,
                        padding: 15,
                        font: { family: 'Inter', size: 11 }
                    }
                },
                tooltip: {
                    backgroundColor: '#1e2638',
                    titleColor: '#f3f4f6',
                    bodyColor: '#e5e7eb',
                    padding: 10,
                    font: { family: 'Inter' }
                }
            }
        }
    });
}

// QUICK ADD LISTENERS
let listenersBound = false;
function setupDashboardListeners() {
    if (listenersBound) return;
    
    // Quick Add Floating Button
    document.getElementById('quick-add-btn').addEventListener('click', () => {
        populateCategorySelect('expense-category');
        
        // Reset Form values
        const form = document.getElementById('expense-form');
        form.reset();
        document.getElementById('expense-form-id').value = '';
        document.getElementById('expense-date').value = new Date().toISOString().substring(0, 10);
        document.getElementById('expense-modal-title').textContent = 'Log Expense';
        document.getElementById('category-suggestion-badge').classList.add('hidden');
        
        openModal('expense-modal');
    });
    
    // Suggest Category while typing note/merchant
    const noteInput = document.getElementById('expense-note');
    const merchantInput = document.getElementById('expense-merchant');
    
    const autoSuggest = () => {
        const query = (noteInput.value + " " + merchantInput.value).toLowerCase();
        const suggestion = suggestCategory(query);
        const select = document.getElementById('expense-category');
        const badge = document.getElementById('category-suggestion-badge');
        
        if (suggestion) {
            // Find option value matching name
            for (let i = 0; i < select.options.length; i++) {
                if (select.options[i].text.toLowerCase() === suggestion.toLowerCase()) {
                    select.selectedIndex = i;
                    badge.classList.remove('hidden');
                    return;
                }
            }
        }
        badge.classList.add('hidden');
    };
    
    noteInput.addEventListener('input', autoSuggest);
    merchantInput.addEventListener('input', autoSuggest);
    
    // Form Submit
    document.getElementById('expense-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const expenseId = document.getElementById('expense-form-id').value;
        const amount = parseFloat(document.getElementById('expense-amount').value);
        const note = document.getElementById('expense-note').value;
        const merchant = document.getElementById('expense-merchant').value;
        const category_id = parseInt(document.getElementById('expense-category').value);
        const payment_mode = document.getElementById('expense-payment').value;
        const expense_date = document.getElementById('expense-date').value;
        
        const payload = {
            category_id,
            amount,
            payment_mode,
            expense_date,
            note,
            merchant
        };
        
        try {
            let res;
            if (expenseId) {
                payload.expense_id = parseInt(expenseId);
                res = await fetchAPI('/expenses', {
                    method: 'PUT',
                    body: JSON.stringify(payload)
                });
            } else {
                res = await fetchAPI('/expenses', {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });
            }
            
            closeAllModals();
            
            // Reload Dashboard
            await loadDashboardData();
            
            // Reload Alerts
            await loadNotifications();
            
        } catch (err) {
            alert('Failed to save expense: ' + err.message);
        }
    });
    
    listenersBound = true;
}

// Auto-categorization Keyword Logic
function suggestCategory(text) {
    const keywordMap = {
        'food': ['uber eats', 'swiggy', 'zomato', 'restaurant', 'cafe', 'coffee', 'lunch', 'dinner', 'pizza', 'burger', 'starbucks', 'food', 'snack', 'grocery', 'groceries', 'tea', 'eat', 'mcdonald', 'kfc'],
        'travel': ['uber', 'cab', 'taxi', 'ola', 'train', 'flight', 'fuel', 'gas', 'petrol', 'bus', 'auto', 'metro', 'commute', 'airline', 'locomotive'],
        'bills': ['rent', 'electricity', 'water', 'gas bill', 'wifi', 'internet', 'phone', 'recharge', 'netflix', 'spotify', 'subscription', 'bill', 'insurance', 'tax', 'utility', 'utilities'],
        'shopping': ['amazon', 'flipkart', 'clothes', 'shoes', 'mall', 'myntra', 'zara', 'shopping', 'nike', 'tshirt', 'jeans', 'electronics', 'gadget'],
        'entertainment': ['movie', 'cinema', 'theater', 'game', 'arcade', 'concert', 'booking', 'show', 'pub', 'club', 'bar', 'alcohol', 'beer', 'ticket']
    };
    
    for (const [category, keywords] of Object.entries(keywordMap)) {
        for (const word of keywords) {
            if (text.includes(word)) {
                return category; // returns Category name e.g. 'food'
            }
        }
    }
    return null;
}

export function populateCategorySelect(selectElementId, selectedId = null) {
    const select = document.getElementById(selectElementId);
    if (!select) return;
    
    select.innerHTML = state.categories.map(cat => {
        const isSelected = cat.category_id === selectedId ? 'selected' : '';
        return `<option value="${cat.category_id}" ${isSelected}>${cat.name}</option>`;
    }).join('');
}

// EXPENSES LIST VIEW COMPONENT
import { fetchAPI } from '../api.js';
import { state, openModal, loadNotifications } from '../app.js';
import { populateCategorySelect } from './dashboard.js';

let expensesListenersBound = false;

export async function renderExpenses() {
    setupExpensesListeners();
    populateCategorySelect('filter-category');
    
    // Insert "All Categories" default option
    const filterCat = document.getElementById('filter-category');
    filterCat.innerHTML = `<option value="">All Categories</option>` + filterCat.innerHTML;
    
    await loadExpensesList();
}

async function loadExpensesList() {
    const search = document.getElementById('filter-search').value;
    const category_id = document.getElementById('filter-category').value;
    const payment_mode = document.getElementById('filter-payment-mode').value;
    const start_date = document.getElementById('filter-start-date').value;
    const end_date = document.getElementById('filter-end-date').value;
    
    // Build query params
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (category_id) params.append('category_id', category_id);
    if (payment_mode) params.append('payment_mode', payment_mode);
    if (start_date) params.append('start_date', start_date);
    if (end_date) params.append('end_date', end_date);
    
    try {
        const expenses = await fetchAPI(`/expenses?${params.toString()}`);
        renderExpensesTable(expenses);
    } catch (err) {
        console.error('Failed to load expenses list:', err);
    }
}

function renderExpensesTable(expenses) {
    const tbody = document.getElementById('expenses-list-tbody');
    if (expenses.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">No expenses found matching the criteria.</td></tr>`;
        return;
    }
    
    tbody.innerHTML = expenses.map(e => {
        const dateObj = new Date(e.expense_date);
        const formattedDate = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        
        return `
            <tr data-expense-id="${e.expense_id}">
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
                <td class="text-right" style="font-weight: 600; color: var(--text-primary); font-size: 1.05rem;">$${e.amount.toFixed(2)}</td>
                <td class="text-center">
                    <div class="action-btn-group">
                        <button class="table-action-btn edit-expense-btn" title="Edit">
                            <i data-lucide="edit" style="width:16px;height:16px;"></i>
                        </button>
                        <button class="table-action-btn delete-action delete-expense-btn" title="Delete">
                            <i data-lucide="trash-2" style="width:16px;height:16px;"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
    
    // Bind Action buttons
    tbody.querySelectorAll('.edit-expense-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const row = btn.closest('tr');
            const expenseId = row.getAttribute('data-expense-id');
            const expenseObj = expenses.find(item => item.expense_id === parseInt(expenseId));
            if (expenseObj) {
                openEditModal(expenseObj);
            }
        });
    });
    
    tbody.querySelectorAll('.delete-expense-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const row = btn.closest('tr');
            const expenseId = row.getAttribute('data-expense-id');
            if (confirm('Are you sure you want to delete this expense?')) {
                try {
                    await fetchAPI('/expenses', {
                        method: 'DELETE',
                        body: JSON.stringify({ expense_id: expenseId })
                    });
                    loadExpensesList();
                    loadNotifications(); // Refresh warning notifications
                } catch (err) {
                    alert('Deletion failed: ' + err.message);
                }
            }
        });
    });
    
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

function openEditModal(expense) {
    populateCategorySelect('expense-category', expense.category_id);
    
    document.getElementById('expense-form-id').value = expense.expense_id;
    document.getElementById('expense-amount').value = expense.amount;
    document.getElementById('expense-note').value = expense.note || '';
    document.getElementById('expense-merchant').value = expense.merchant || '';
    document.getElementById('expense-payment').value = expense.payment_mode;
    document.getElementById('expense-date').value = expense.expense_date;
    
    document.getElementById('expense-modal-title').textContent = 'Edit Expense';
    document.getElementById('category-suggestion-badge').classList.add('hidden');
    
    openModal('expense-modal');
}

function setupExpensesListeners() {
    if (expensesListenersBound) return;
    
    const triggerSearch = () => {
        loadExpensesList();
    };
    
    // Hook change inputs
    document.getElementById('filter-search').addEventListener('input', debounce(triggerSearch, 300));
    document.getElementById('filter-category').addEventListener('change', triggerSearch);
    document.getElementById('filter-payment-mode').addEventListener('change', triggerSearch);
    document.getElementById('filter-start-date').addEventListener('change', triggerSearch);
    document.getElementById('filter-end-date').addEventListener('change', triggerSearch);
    
    // Reset Filters button
    document.getElementById('reset-filters-btn').addEventListener('click', () => {
        document.getElementById('filter-search').value = '';
        document.getElementById('filter-category').value = '';
        document.getElementById('filter-payment-mode').value = '';
        document.getElementById('filter-start-date').value = '';
        document.getElementById('filter-end-date').value = '';
        loadExpensesList();
    });
    
    expensesListenersBound = true;
}

// Debounce helper to avoid server spam on search typing
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

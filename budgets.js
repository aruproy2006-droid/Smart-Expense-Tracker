// BUDGETS VIEW COMPONENT
import { fetchAPI } from '../api.js';
import { state, openModal, closeAllModals, loadNotifications } from '../app.js';
import { populateCategorySelect } from './dashboard.js';

let budgetListenersBound = false;

export async function renderBudgets() {
    setupBudgetListeners();
    updateMonthLabel();
    await loadBudgetsList();
}

function updateMonthLabel() {
    const monthNames = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ];
    document.getElementById('budget-month-label').textContent = `${monthNames[state.currentMonth - 1]} ${state.currentYear}`;
}

async function loadBudgetsList() {
    try {
        // Fetch budgets set for current month
        const budgets = await fetchAPI(`/budgets?month=${state.currentMonth}&year=${state.currentYear}`);
        
        // Fetch current month dashboard summary to match actual category spendings
        const summary = await fetchAPI(`/dashboard?month=${state.currentMonth}&year=${state.currentYear}`);
        const spendingMap = {};
        summary.category_breakdown.forEach(cat => {
            spendingMap[cat.category_id] = cat.actual_spend;
        });
        
        renderBudgetsGrid(budgets, spendingMap);
    } catch (err) {
        console.error('Failed to load budgets list:', err);
    }
}

function renderBudgetsGrid(budgets, spendingMap) {
    const container = document.getElementById('budgets-detailed-container');
    
    // Create a map of active budgets by category
    const budgetMap = {};
    budgets.forEach(b => {
        budgetMap[b.category_id] = b;
    });
    
    // Render all categories, showing budget limit if exists
    container.innerHTML = state.categories.map(cat => {
        const budget = budgetMap[cat.category_id];
        const actualSpend = spendingMap[cat.category_id] || 0.0;
        
        if (budget) {
            const pct = budget.limit_amount > 0 ? (actualSpend / budget.limit_amount) * 100 : 0;
            let fillClass = 'fill-safe';
            if (pct >= 100) fillClass = 'fill-danger';
            else if (pct >= 80) fillClass = 'fill-warning';
            
            const remaining = budget.limit_amount - actualSpend;
            const isOver = remaining < 0;
            
            return `
                <div class="budget-detail-card card">
                    <div class="budget-detail-header">
                        <div class="budget-detail-icon" style="background-color: ${cat.color_hex};">
                            <i data-lucide="${cat.icon}"></i>
                        </div>
                        <div class="budget-detail-title">
                            <h3>${cat.name}</h3>
                            <span class="status-pill ${pct >= 100 ? 'paused' : 'active'}" style="font-size:0.7rem;">
                                ${pct >= 100 ? 'Exceeded' : 'Active Limit'}
                            </span>
                        </div>
                        <button class="table-action-btn edit-budget-btn" data-category-id="${cat.category_id}" data-limit="${budget.limit_amount}" data-alert-pct="${budget.alert_threshold_pct}" title="Edit Limit">
                            <i data-lucide="edit-3" style="width:16px;height:16px;"></i>
                        </button>
                    </div>
                    
                    <div class="budget-amount-row">
                        <span class="budget-amount-spent">$${actualSpend.toFixed(2)}</span>
                        <span class="budget-amount-limit">limit $${budget.limit_amount.toFixed(0)}</span>
                    </div>
                    
                    <div class="budget-detail-progress">
                        <div class="budget-bar-track">
                            <div class="budget-bar-fill ${fillClass}" style="width: ${Math.min(pct, 100)}%;"></div>
                        </div>
                    </div>
                    
                    <div class="budget-detail-stats">
                        <span>${pct.toFixed(0)}% Used</span>
                        <span style="font-weight: 600; color: ${isOver ? 'var(--color-danger)' : 'var(--color-success)'};">
                            ${isOver ? `Over by $${Math.abs(remaining).toFixed(2)}` : `Remaining $${remaining.toFixed(2)}`}
                        </span>
                    </div>
                </div>
            `;
        } else {
            // No budget limit set category card
            return `
                <div class="budget-detail-card card" style="border-style: dashed; background: transparent; display:flex; flex-direction:column; justify-content:center; align-items:center; min-height: 190px; text-align:center;">
                    <div class="budget-detail-icon mb-4" style="background-color: ${cat.color_hex}2a; color: ${cat.color_hex}; width: 48px; height: 48px;">
                        <i data-lucide="${cat.icon}"></i>
                    </div>
                    <h3 style="margin-bottom:6px;">${cat.name}</h3>
                    <p class="text-muted" style="font-size:0.82rem; margin-bottom:16px;">No spending limit defined for this month</p>
                    <button class="btn btn-secondary btn-sm set-category-budget-btn" data-category-id="${cat.category_id}">
                        Set Monthly Limit
                    </button>
                </div>
            `;
        }
    }).join('');
    
    // Bind Set Budget CTAs
    container.querySelectorAll('.set-category-budget-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const categoryId = parseInt(btn.getAttribute('data-category-id'));
            openBudgetSetupModal(categoryId);
        });
    });
    
    // Bind Edit Budget limits
    container.querySelectorAll('.edit-budget-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const categoryId = parseInt(btn.getAttribute('data-category-id'));
            const limit = parseFloat(btn.getAttribute('data-limit'));
            const alertPct = parseInt(btn.getAttribute('data-alert-pct'));
            openBudgetSetupModal(categoryId, limit, alertPct);
        });
    });
    
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

function openBudgetSetupModal(categoryId, limit = '', alertPct = 80) {
    populateCategorySelect('budget-category', categoryId);
    
    // Lock category dropdown selection for convenience if pre-selected
    document.getElementById('budget-category').value = categoryId;
    document.getElementById('budget-limit').value = limit;
    document.getElementById('budget-alert-pct').value = alertPct;
    
    openModal('budget-setup-modal');
}

function setupBudgetListeners() {
    if (budgetListenersBound) return;
    
    // Month navigation buttons
    document.getElementById('budget-prev-month').addEventListener('click', () => {
        state.currentMonth -= 1;
        if (state.currentMonth < 1) {
            state.currentMonth = 12;
            state.currentYear -= 1;
        }
        updateMonthLabel();
        loadBudgetsList();
    });
    
    document.getElementById('budget-next-month').addEventListener('click', () => {
        state.currentMonth += 1;
        if (state.currentMonth > 12) {
            state.currentMonth = 1;
            state.currentYear += 1;
        }
        updateMonthLabel();
        loadBudgetsList();
    });
    
    // Upper right "Set Budget" trigger button
    document.getElementById('add-budget-btn').addEventListener('click', () => {
        openBudgetSetupModal(state.categories[0]?.category_id);
    });
    
    // Save budget limit form submit
    document.getElementById('budget-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const category_id = parseInt(document.getElementById('budget-category').value);
        const limit_amount = parseFloat(document.getElementById('budget-limit').value);
        const alert_threshold_pct = parseInt(document.getElementById('budget-alert-pct').value);
        
        const payload = {
            category_id,
            limit_amount,
            alert_threshold_pct,
            month: state.currentMonth,
            year: state.currentYear
        };
        
        try {
            await fetchAPI('/budgets', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            closeAllModals();
            loadBudgetsList();
            loadNotifications(); // Reload alerts instantly
        } catch (err) {
            alert('Failed to save budget limit: ' + err.message);
        }
    });
    
    budgetListenersBound = true;
}

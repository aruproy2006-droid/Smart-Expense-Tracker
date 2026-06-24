// RECURRING EXPENSES RULES COMPONENT
import { fetchAPI } from '../api.js';
import { state, openModal, closeAllModals } from '../app.js';
import { populateCategorySelect } from './dashboard.js';

let recurringListenersBound = false;

export async function renderRecurring() {
    setupRecurringListeners();
    await loadRecurringRules();
}

async function loadRecurringRules() {
    try {
        const rules = await fetchAPI('/recurring');
        renderRecurringTable(rules);
    } catch (err) {
        console.error('Failed to load recurring rules list:', err);
    }
}

function renderRecurringTable(rules) {
    const tbody = document.getElementById('recurring-list-tbody');
    if (rules.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">No recurring expense rules set up yet.</td></tr>`;
        return;
    }
    
    tbody.innerHTML = rules.map(r => {
        const dateObj = new Date(r.next_due_date);
        const formattedDate = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        const isActive = r.is_active === 1;
        
        return `
            <tr data-rule-id="${r.recurring_rule_id}">
                <td>
                    <span class="category-indicator" style="background-color: ${r.category_color}1a; color: ${r.category_color};">
                        <span class="category-icon-circle" style="background-color: ${r.category_color};">
                            <i data-lucide="${r.category_icon}"></i>
                        </span>
                        ${r.category_name}
                    </span>
                </td>
                <td style="font-weight: 600; color: var(--text-primary); font-size: 1.05rem;">$${r.amount.toFixed(2)}</td>
                <td><span class="payment-mode-tag" style="text-transform: capitalize;">${r.frequency}</span></td>
                <td style="font-size: 0.85rem;" class="text-muted">${formattedDate}</td>
                <td>
                    <span class="status-pill ${isActive ? 'active' : 'paused'}">
                        ${isActive ? 'Active' : 'Paused'}
                    </span>
                </td>
                <td class="text-center">
                    <div class="action-btn-group">
                        <button class="table-action-btn edit-rule-btn" title="Edit Rule">
                            <i data-lucide="edit" style="width:16px;height:16px;"></i>
                        </button>
                        <button class="table-action-btn delete-action delete-rule-btn" title="Delete Rule">
                            <i data-lucide="trash-2" style="width:16px;height:16px;"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
    
    // Bind Edit Action
    tbody.querySelectorAll('.edit-rule-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const row = btn.closest('tr');
            const ruleId = parseInt(row.getAttribute('data-rule-id'));
            const rule = rules.find(r => r.recurring_rule_id === ruleId);
            if (rule) {
                openEditRuleModal(rule);
            }
        });
    });
    
    // Bind Delete Action
    tbody.querySelectorAll('.delete-rule-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const row = btn.closest('tr');
            const ruleId = row.getAttribute('data-rule-id');
            if (confirm('Are you sure you want to delete this recurring rule?')) {
                try {
                    await fetchAPI('/recurring', {
                        method: 'DELETE',
                        body: JSON.stringify({ recurring_rule_id: ruleId })
                    });
                    loadRecurringRules();
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

function openEditRuleModal(rule) {
    populateCategorySelect('recurring-category', rule.category_id);
    
    document.getElementById('recurring-form-id').value = rule.recurring_rule_id;
    document.getElementById('recurring-amount').value = rule.amount;
    document.getElementById('recurring-frequency').value = rule.frequency;
    document.getElementById('recurring-due').value = rule.next_due_date;
    document.getElementById('recurring-active').value = rule.is_active;
    
    document.getElementById('recurring-status-container').classList.remove('hidden');
    document.getElementById('recurring-modal-title').textContent = 'Edit Recurring Rule';
    
    openModal('recurring-setup-modal');
}

function setupRecurringListeners() {
    if (recurringListenersBound) return;
    
    // Upper Add Rule CTA
    document.getElementById('add-recurring-btn').addEventListener('click', () => {
        populateCategorySelect('recurring-category');
        
        // Reset rule form values
        const form = document.getElementById('recurring-form');
        form.reset();
        document.getElementById('recurring-form-id').value = '';
        document.getElementById('recurring-due').value = new Date().toISOString().substring(0, 10);
        document.getElementById('recurring-status-container').classList.add('hidden');
        document.getElementById('recurring-modal-title').textContent = 'Setup Recurring Expense';
        
        openModal('recurring-setup-modal');
    });
    
    // Form Submit (Create or Update)
    document.getElementById('recurring-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const ruleId = document.getElementById('recurring-form-id').value;
        const category_id = parseInt(document.getElementById('recurring-category').value);
        const amount = parseFloat(document.getElementById('recurring-amount').value);
        const frequency = document.getElementById('recurring-frequency').value;
        const next_due_date = document.getElementById('recurring-due').value;
        const is_active = parseInt(document.getElementById('recurring-active').value || '1');
        
        const payload = {
            category_id,
            amount,
            frequency,
            next_due_date
        };
        
        try {
            if (ruleId) {
                payload.recurring_rule_id = parseInt(ruleId);
                payload.is_active = is_active;
                await fetchAPI('/recurring', {
                    method: 'PUT',
                    body: JSON.stringify(payload)
                });
            } else {
                await fetchAPI('/recurring', {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });
            }
            closeAllModals();
            loadRecurringRules();
        } catch (err) {
            alert('Failed to save recurring rule: ' + err.message);
        }
    });
    
    recurringListenersBound = true;
}

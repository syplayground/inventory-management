<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div class="card budget-card">
      <div class="card-header">
        <h3 class="card-title">{{ t('restocking.budgetLabel') }}</h3>
      </div>
      <div class="budget-controls">
        <input
          type="range"
          min="0"
          max="40000"
          step="500"
          v-model.number="budget"
          class="budget-slider"
        >
        <div class="budget-input-group">
          <span class="budget-currency">{{ currencySymbol }}</span>
          <input
            type="number"
            min="0"
            max="40000"
            step="500"
            v-model.number="budget"
            class="budget-number"
          >
        </div>
      </div>
      <p class="budget-hint">{{ t('restocking.budgetHint') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div v-if="successMessage" class="success-banner">
        <p>{{ successMessage }}</p>
        <p class="success-note">{{ t('restocking.orderSuccessNote') }}</p>
        <router-link to="/orders" class="success-link">{{ t('restocking.viewOrder') }}</router-link>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.totalCost') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ totalCost.toLocaleString() }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.remainingBudget') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ remainingBudget.toLocaleString() }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.itemsRecommended') }}</div>
          <div class="stat-value">{{ t('restocking.itemsRecommendedRatio', { shown: items.length, total: consideredCount }) }}</div>
        </div>
        <div class="stat-card danger">
          <div class="stat-label">{{ t('restocking.maxLeadTime') }}</div>
          <div class="stat-value">{{ maxLeadTimeDays }} {{ t('restocking.days') }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }}</h3>
          <button
            class="place-order-btn"
            :disabled="items.length === 0 || submitting"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="consideredCount === 0" class="empty-state">
          {{ t('restocking.noRestockingNeeded') }}
        </div>
        <div v-else-if="items.length === 0" class="empty-state">
          {{ t('restocking.increaseBudget') }}
        </div>
        <div v-else class="table-container">
          <table class="restocking-table">
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.category') }}</th>
                <th>{{ t('restocking.table.currentStock') }}</th>
                <th>{{ t('restocking.table.forecastedDemand') }}</th>
                <th>{{ t('restocking.table.shortfall') }}</th>
                <th>{{ t('restocking.table.recommendedQty') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineCost') }}</th>
                <th>{{ t('restocking.table.supplier') }}</th>
                <th>{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="item.sku">
                <td><strong>{{ item.sku }}</strong></td>
                <td>{{ translateProductName(item.item_name) }}</td>
                <td>{{ item.category }}</td>
                <td>{{ item.current_stock.toLocaleString() }}</td>
                <td>{{ item.forecasted_demand.toLocaleString() }}</td>
                <td>{{ item.shortfall.toLocaleString() }}</td>
                <td>{{ item.recommended_quantity.toLocaleString() }}</td>
                <td>{{ currencySymbol }}{{ item.unit_cost.toLocaleString() }}</td>
                <td>{{ currencySymbol }}{{ item.line_cost.toLocaleString() }}</td>
                <td>{{ item.supplier }}</td>
                <td>{{ item.lead_time_days }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName } = useI18n()

    const currencySymbol = computed(() => {
      return currentCurrency.value === 'JPY' ? '¥' : '$'
    })

    const budget = ref(15000)
    const loading = ref(true)
    const error = ref(null)
    const submitting = ref(false)
    const successMessage = ref(null)

    const totalCost = ref(0)
    const remainingBudget = ref(0)
    const maxLeadTimeDays = ref(0)
    const consideredCount = ref(0)
    const items = ref([])

    // No @vueuse/core dependency in this project - debounce recommendation
    // fetches with a small local setTimeout-based helper instead of a library.
    let debounceHandle = null
    const debounce = (fn, delay) => {
      if (debounceHandle) clearTimeout(debounceHandle)
      debounceHandle = setTimeout(fn, delay)
    }

    const loadRecommendations = async () => {
      try {
        loading.value = true
        error.value = null
        const data = await api.getRestockRecommendations(budget.value)
        totalCost.value = data.total_cost
        remainingBudget.value = data.remaining_budget
        maxLeadTimeDays.value = data.max_lead_time_days
        consideredCount.value = data.considered_count
        items.value = data.items
      } catch (err) {
        error.value = 'Failed to load restocking recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    watch(budget, () => {
      successMessage.value = null
      debounce(loadRecommendations, 300)
    })

    const placeOrder = async () => {
      if (items.value.length === 0 || submitting.value) return
      submitting.value = true
      error.value = null
      try {
        const payload = {
          budget: budget.value,
          items: items.value.map(i => ({ sku: i.sku, quantity: i.recommended_quantity }))
        }
        const order = await api.submitRestockOrder(payload)
        successMessage.value = t('restocking.orderSuccess', { orderNumber: order.order_number })
      } catch (err) {
        error.value = 'Failed to place restocking order: ' + err.message
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadRecommendations)

    return {
      t,
      currencySymbol,
      translateProductName,
      budget,
      loading,
      error,
      submitting,
      successMessage,
      totalCost,
      remainingBudget,
      maxLeadTimeDays,
      consideredCount,
      items,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  margin-bottom: 1.5rem;
}

.budget-controls {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.budget-slider {
  flex: 1;
  accent-color: #2563eb;
  height: 6px;
}

.budget-input-group {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
  min-width: 140px;
}

.budget-currency {
  color: #64748b;
  font-weight: 600;
}

.budget-number {
  border: none;
  outline: none;
  width: 100%;
  font-size: 0.938rem;
  font-weight: 600;
  color: #0f172a;
}

.budget-hint {
  margin-top: 0.625rem;
  color: #64748b;
  font-size: 0.813rem;
}

.place-order-btn {
  background: #2563eb;
  color: white;
  border: none;
  padding: 0.625rem 1.25rem;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
  transition: background 0.2s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.empty-state {
  text-align: center;
  padding: 2.5rem 1rem;
  color: #64748b;
  font-size: 0.938rem;
}

.success-banner {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.25rem;
  font-size: 0.938rem;
}

.success-note {
  margin-top: 0.375rem;
  font-size: 0.813rem;
  color: #047857;
}

.success-link {
  display: inline-block;
  margin-top: 0.5rem;
  color: #059669;
  font-weight: 600;
  text-decoration: underline;
}
</style>

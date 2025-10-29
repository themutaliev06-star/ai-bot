console.log('🚀 AI Trading Bot Dashboard loaded');

// Функции для форматирования чисел
function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value);
}

function formatPercent(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'percent',
        minimumFractionDigits: 1,
        maximumFractionDigits: 1
    }).format(value / 100);
}

// Простой класс для управления дашбордом
class SimpleDashboard {
    constructor() {
        this.init();
    }

    async init() {
        console.log('🤖 Инициализация дашборда...');
        await this.loadData();
        
        // Авто-обновление каждые 5 секунд
        setInterval(() => {
            this.loadData();
        }, 5000);
    }

    async loadData() {
        try {
            await this.loadBalance();
            await this.loadPositions();
        } catch (error) {
            console.error('❌ Ошибка загрузки данных:', error);
        }
    }

    async loadBalance() {
        try {
            const response = await fetch('/api/balance');
            if (!response.ok) throw new Error('API error');
            const data = await response.json();
            this.updateBalance(data);
        } catch (error) {
            console.error('Ошибка загрузки баланса:', error);
            this.showError('balance', 'Ошибка загрузки');
        }
    }

    async loadPositions() {
        try {
            const response = await fetch('/api/positions');
            if (!response.ok) throw new Error('API error');
            const data = await response.json();
            this.updatePositions(data);
        } catch (error) {
            console.error('Ошибка загрузки позиций:', error);
            this.showError('positions', 'Ошибка загрузки позиций');
        }
    }

    updateBalance(data) {
        console.log('📊 Обновление баланса:', data);
        
        // Обновляем элементы на странице
        const elements = {
            'total-balance': formatCurrency(data.total_balance || 0),
            'available-balance': formatCurrency(data.available_balance || 0),
            'pnl-total': formatCurrency(data.pnl_total || 0),
            'pnl-today': formatCurrency(data.pnl_today || 0),
            'win-rate': formatPercent(data.win_rate || 0),
            'sharpe-ratio': (data.sharpe_ratio || 0).toFixed(2),
            'max-drawdown': formatPercent(data.max_drawdown || 0)
        };

        for (const [id, value] of Object.entries(elements)) {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
                
                // Добавляем классы для цветов
                if (id.includes('pnl')) {
                    const numValue = data[id.replace('-', '_')] || 0;
                    element.className = numValue >= 0 ? 'metric-value positive' : 'metric-value negative';
                }
                
                if (id === 'max-drawdown') {
                    const numValue = data.max_drawdown || 0;
                    element.className = numValue >= 0 ? 'metric-value positive' : 'metric-value negative';
                }
            }
        }
    }

    updatePositions(positions) {
        console.log('📈 Обновление позиций:', positions);
        const container = document.getElementById('positions-container');
        if (!container) return;

        if (!positions || positions.length === 0) {
            container.innerHTML = '<div class="loading">🚫 Нет активных позиций</div>';
            return;
        }

        container.innerHTML = positions.map(position => `
            <div class="position-item">
                <div class="position-symbol">${position.symbol}</div>
                <div class="position-details">
                    <span>Размер: ${position.size}</span>
                    <span>Вход: ${formatCurrency(position.entry_price)}</span>
                    <span>Текущая: ${formatCurrency(position.current_price)}</span>
                </div>
                <div class="position-pnl ${position.unrealized_pnl >= 0 ? 'positive' : 'negative'}">
                    PnL: ${formatCurrency(position.unrealized_pnl || 0)}
                </div>
            </div>
        `).join('');
    }

    showError(elementId, message) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = message;
            element.style.color = '#e74c3c';
        }
    }
}

// Запускаем когда страница загружена
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        new SimpleDashboard();
    });
} else {
    new SimpleDashboard();
}
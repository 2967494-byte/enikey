/**
 * PulseAPI - Централизованный сервис для работы с данными новостей и статей.
 * Инкапсулирует логику хранения (localStorage или Supabase).
 */
const PulseAPI = {
    _KEYS: {
        PUBLISHED: 'enikey_pulse_published',
        PENDING: 'enikey_pulse_pending',
        TASKS: 'enikey_pulse_agent_tasks',
        SETTINGS: 'enikey_pulse_agent_settings'
    },

    /**
     * Получить глобальные настройки агента (API)
     */
    getAgentSettings: async function() {
        const defaultSettings = {
            provider: 'openai',
            key: '',
            url: 'https://api.openai.com/v1'
        };

        try {
            const res = await fetch(`${window.API_CONFIG.BASE_URL}/config`);
            if (res.ok) return await res.json();
        } catch (e) {
            console.warn('Backend unavailable, using localStorage fallback');
        }

        const raw = localStorage.getItem(this._KEYS.SETTINGS);
        return raw ? JSON.parse(raw) : defaultSettings;
    },

    /**
     * Обновить глобальные настройки
     */
    updateAgentSettings: async function(settings) {
        try {
            await fetch(`${window.API_CONFIG.BASE_URL}/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
        } catch (e) {}
        localStorage.setItem(this._KEYS.SETTINGS, JSON.stringify(settings));
        return settings;
    },

    /**
     * Получить список всех задач ИИ
     */
    getAgentTasks: async function() {
        try {
            const res = await fetch(`${window.API_CONFIG.BASE_URL}/tasks`);
            if (res.ok) return await res.json();
        } catch (e) {}

        const raw = localStorage.getItem(this._KEYS.TASKS);
        return raw ? JSON.parse(raw) : [];
    },

    /**
     * Сохранить или обновить задачу
     */
    saveAgentTask: async function(task) {
        try {
            const method = task.id ? 'PUT' : 'POST';
            const url = task.id ? `${window.API_CONFIG.BASE_URL}/tasks/${task.id}` : `${window.API_CONFIG.BASE_URL}/tasks`;
            const res = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(task)
            });
            if (res.ok) return await res.json();
        } catch (e) {}

        // Fallback to localStorage
        let tasks = JSON.parse(localStorage.getItem(this._KEYS.TASKS) || '[]');
        if (task.id) {
            const index = tasks.findIndex(t => t.id === task.id);
            if (index !== -1) tasks[index] = task;
            else tasks.push(task);
        } else {
            task.id = Date.now();
            tasks.push(task);
        }
        localStorage.setItem(this._KEYS.TASKS, JSON.stringify(tasks));
        return task;
    },

    /**
     * Удалить задачу
     */
    deleteAgentTask: async function(id) {
        try {
            await fetch(`${window.API_CONFIG.BASE_URL}/tasks/${id}`, { method: 'DELETE' });
        } catch (e) {}
        
        let tasks = JSON.parse(localStorage.getItem(this._KEYS.TASKS) || '[]');
        tasks = tasks.filter(t => t.id !== id);
        localStorage.setItem(this._KEYS.TASKS, JSON.stringify(tasks));
        return true;
    },

    /**
     * Получить опубликованный контент
     */
    getPublished: async function() {
        try {
            const res = await fetch(`${window.API_CONFIG.BASE_URL}/published`);
            if (res.ok) return await res.json();
        } catch (e) {}

        const raw = localStorage.getItem(this._KEYS.PUBLISHED);
        if (!raw) return { news: [], articles: [] };
        return JSON.parse(raw);
    },

    /**
     * Получить очередь на модерацию
     */
    getPending: async function() {
        try {
            const res = await fetch(`${window.API_CONFIG.BASE_URL}/pending`);
            if (res.ok) return await res.json();
        } catch (e) {}

        const raw = localStorage.getItem(this._KEYS.PENDING);
        return raw ? JSON.parse(raw) : [];
    },

    /**
     * Добавить черновик в очередь
     */
    addPending: async function(item) {
        try {
            await fetch(`${window.API_CONFIG.BASE_URL}/pending`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(item)
            });
            return this.getPending();
        } catch (e) {}

        const pending = await this.getPending();
        pending.unshift(item);
        localStorage.setItem(this._KEYS.PENDING, JSON.stringify(pending));
        return pending;
    },

    /**
     * Обновить черновик (ручное редактирование)
     */
    updatePending: async function(index, newData) {
        const pending = await this.getPending();
        if (pending[index]) {
            const item = pending[index];
            try {
                await fetch(`${window.API_CONFIG.BASE_URL}/pending/${item.id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(newData)
                });
            } catch (e) {}
            
            pending[index] = { ...item, ...newData };
            localStorage.setItem(this._KEYS.PENDING, JSON.stringify(pending));
        }
        return pending;
    },

    /**
     * Одобрить публикацию
     */
    approve: async function(index) {
        const pending = await this.getPending();
        if (pending[index]) {
            const item = pending[index];
            try {
                await fetch(`${window.API_CONFIG.BASE_URL}/approve/${item.id}`, { method: 'POST' });
            } catch (e) {}
            
            pending.splice(index, 1);
            localStorage.setItem(this._KEYS.PENDING, JSON.stringify(pending));
        }
        return { pending, published: await this.getPublished() };
    },

    /**
     * Отправить на доработку с комментарием
     */
    rework: async function(index, comment) {
        const pending = await this.getPending();
        if (pending[index]) {
            const item = pending[index];
            try {
                await fetch(`${window.API_CONFIG.BASE_URL}/pending/${item.id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: 'rework', reworkReason: comment })
                });
            } catch (e) {}
            
            pending[index].status = 'rework';
            pending[index].reworkReason = comment;
            localStorage.setItem(this._KEYS.PENDING, JSON.stringify(pending));
        }
        return pending;
    },

    /**
     * Удалить черновик
     */
    remove: async function(index) {
        const pending = await this.getPending();
        if (pending[index]) {
            try {
                await fetch(`${window.API_CONFIG.BASE_URL}/pending/${pending[index].id}`, { method: 'DELETE' });
            } catch (e) {}
            pending.splice(index, 1);
            localStorage.setItem(this._KEYS.PENDING, JSON.stringify(pending));
        }
        return pending;
    }
};

window.PulseAPI = PulseAPI;

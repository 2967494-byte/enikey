/**
 * PulseAgent - Имитация работы ИИ-агента, который готовит материалы.
 */
const PulseAgent = {
    /**
     * Сгенерировать новый черновик на основе конкретной задачи
     */
    generateDraft: async function(task) {
        if (!task) {
            const tasks = await window.PulseAPI.getAgentTasks();
            task = tasks[0];
        }
        if (!task) return null;

        try {
            const res = await fetch(`${window.API_CONFIG.BASE_URL}/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task })
            });
            
            if (!res.ok) throw new Error('API Request Failed');
            
            const draft = await res.json();
            if (window.PulseAPI) {
                await window.PulseAPI.addPending(draft);
            }
            return draft;
        } catch (e) {
            console.warn('Real AI Generation failed, using Mock:', e);
            const topics = [
                { ru: "Квантовое превосходство", en: "Quantum Supremacy", zh: "量子霸权" },
                { ru: "Нейронные интерфейсы", en: "Neural Interfaces", zh: "神经接口" }
            ];
            const topic = topics[Math.floor(Math.random() * topics.length)];
            const draft = {
                id: Date.now().toString(),
                type: task.type,
                status: 'pending',
                title: { ru: `[DRAFT] ${topic.ru}`, en: `[DRAFT] ${topic.en}`, zh: `[DRAFT] ${topic.zh}` },
                summary: { ru: `Описание ${topic.ru}`, en: `Description of ${topic.en}`, zh: `${topic.zh} 的描述` },
                content: { ru: `<p>${topic.ru} контент</p>`, en: `<p>${topic.en} content</p>`, zh: `<p>${topic.zh} 内容</p>` },
                image: 'agency_tech_abstract.png'
            };
            if (window.PulseAPI) await window.PulseAPI.addPending(draft);
            return draft;
        }
    },

    /**
     * Перевести контент через локальный API
     */
    translate: async function(data, langs) {
        const res = await fetch(`${window.API_CONFIG.BASE_URL}/translate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ data, langs })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || 'Translation failed');
        }
        return await res.json();
    }
};

// Экспортируем глобально
window.PulseAgent = PulseAgent;

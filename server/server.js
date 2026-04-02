const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const DB_PATH = path.join(__dirname, 'database.sqlite');

app.use(cors());
app.use(express.json());

// Инициализация базы данных
const db = new sqlite3.Database(DB_PATH, (err) => {
    if (err) console.error('Database connection error:', err);
    else console.log('Connected to SQLite database.');
});

db.serialize(() => {
    // 1. Конфигурация агента
    db.run(`CREATE TABLE IF NOT EXISTS agent_config (
        id INTEGER PRIMARY KEY,
        settings TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);

    // 2. Задачи ИИ
    db.run(`CREATE TABLE IF NOT EXISTS agent_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT,
        schedule TEXT NOT NULL,
        prompt TEXT,
        use_image BOOLEAN DEFAULT 0,
        image_prompt TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);

    // 3. Опубликованный контент
    db.run(`CREATE TABLE IF NOT EXISTS published_content (
        id TEXT PRIMARY KEY,
        type TEXT,
        title TEXT NOT NULL,
        summary TEXT,
        content TEXT,
        image_url TEXT,
        author_name TEXT DEFAULT 'Enikey AI Agent',
        published_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        metadata TEXT DEFAULT '{}'
    )`);

    // 4. Очередь на модерацию
    db.run(`CREATE TABLE IF NOT EXISTS pending_content (
        id TEXT PRIMARY KEY,
        type TEXT,
        title TEXT NOT NULL,
        summary TEXT,
        content TEXT,
        status TEXT DEFAULT 'pending',
        rework_reason TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);
});

// API Эндпоинты

// --- Задачи ИИ ---
app.get('/api/tasks', (req, res) => {
    db.all("SELECT * FROM agent_tasks", [], (err, rows) => {
        if (err) return res.status(500).json({ error: err.message });
        const tasks = rows.map(t => ({
            ...t,
            schedule: JSON.parse(t.schedule),
            useImage: !!t.use_image,
            imagePrompt: t.image_prompt
        }));
        res.json(tasks);
    });
});

app.post('/api/tasks', (req, res) => {
    const t = req.body;
    const schedule = JSON.stringify(t.schedule);
    const sql = `INSERT INTO agent_tasks (name, type, schedule, prompt, use_image, image_prompt) VALUES (?, ?, ?, ?, ?, ?)`;
    db.run(sql, [t.name, t.type, schedule, t.prompt, t.useImage ? 1 : 0, t.imagePrompt], function(err) {
        if (err) return res.status(500).json({ error: err.message });
        res.json({ id: this.lastID, ...t });
    });
});

app.put('/api/tasks/:id', (req, res) => {
    const t = req.body;
    const schedule = JSON.stringify(t.schedule);
    const sql = `UPDATE agent_tasks SET name = ?, type = ?, schedule = ?, prompt = ?, use_image = ?, image_prompt = ? WHERE id = ?`;
    db.run(sql, [t.name, t.type, schedule, t.prompt, t.useImage ? 1 : 0, t.imagePrompt, req.params.id], (err) => {
        if (err) return res.status(500).json({ error: err.message });
        res.json({ success: true });
    });
});

app.delete('/api/tasks/:id', (req, res) => {
    db.run("DELETE FROM agent_tasks WHERE id = ?", req.params.id, (err) => {
        if (err) return res.status(500).json({ error: err.message });
        res.json({ success: true });
    });
});

// --- Настройки ---
app.get('/api/config', (req, res) => {
    db.get("SELECT * FROM agent_config WHERE id = 1", [], (err, row) => {
        if (err) return res.status(500).json({ error: err.message });
        if (!row) return res.json({ settings: { provider: 'openai', key: '', url: 'https://api.openai.com/v1' } });
        res.json(JSON.parse(row.settings));
    });
});

app.post('/api/config', (req, res) => {
    const settings = JSON.stringify(req.body);
    db.run("INSERT OR REPLACE INTO agent_config (id, settings) VALUES (1, ?)", [settings], (err) => {
        if (err) return res.status(500).json({ error: err.message });
        res.json({ success: true });
    });
});

// --- Контент ---
app.get('/api/published', (req, res) => {
    db.all("SELECT * FROM published_content ORDER BY published_at DESC", [], (err, rows) => {
        if (err) return res.status(500).json({ error: err.message });
        const data = rows.map(r => ({
            ...r,
            title: r.title.startsWith('{') ? JSON.parse(r.title) : { ru: r.title },
            content: r.content && r.content.startsWith('{') ? JSON.parse(r.content) : { ru: r.content },
            summary: r.summary && r.summary.startsWith('{') ? JSON.parse(r.summary) : { ru: r.summary }
        }));
        res.json({
            news: data.filter(i => i.type === 'news'),
            articles: data.filter(i => i.type === 'article')
        });
    });
});

app.post('/api/published_direct', (req, res) => {
    const item = req.body;
    const id = item.id || Date.now().toString();
    const sql = `INSERT INTO published_content (id, type, title, summary, content, image_url) VALUES (?, ?, ?, ?, ?, ?)`;
    db.run(sql, [
        id, 
        item.type, 
        JSON.stringify(item.title), 
        JSON.stringify(item.excerpt || item.summary), 
        JSON.stringify(item.content || item.title), 
        item.image || ''
    ], (err) => {
        if (err) return res.status(500).json({ error: err.message });
        res.json({ success: true, id });
    });
});

app.get('/api/pending', (req, res) => {
    db.all("SELECT * FROM pending_content ORDER BY created_at DESC", [], (err, rows) => {
        if (err) return res.status(500).json({ error: err.message });
        const data = rows.map(r => ({
            ...r,
            title: JSON.parse(r.title),
            content: JSON.parse(r.content),
            summary: JSON.parse(r.summary),
            reworkReason: r.rework_reason
        }));
        res.json(data);
    });
});

app.post('/api/pending', (req, res) => {
    const item = req.body;
    const id = item.id || Date.now().toString();
    const sql = `INSERT INTO pending_content (id, type, title, summary, content, status) VALUES (?, ?, ?, ?, ?, ?)`;
    db.run(sql, [id, item.type, JSON.stringify(item.title), JSON.stringify(item.summary), JSON.stringify(item.content), 'pending'], (err) => {
        if (err) return res.status(500).json({ error: err.message });
        res.json({ success: true, id });
    });
});

app.patch('/api/pending/:id', (req, res) => {
    const data = req.body;
    const fields = [];
    const values = [];
    if (data.title) { fields.push('title = ?'); values.push(JSON.stringify(data.title)); }
    if (data.summary) { fields.push('summary = ?'); values.push(JSON.stringify(data.summary)); }
    if (data.content) { fields.push('content = ?'); values.push(JSON.stringify(data.content)); }
    if (data.status) { fields.push('status = ?'); values.push(data.status); }
    if (data.reworkReason) { fields.push('rework_reason = ?'); values.push(data.reworkReason); }
    
    values.push(req.params.id);
    db.run(`UPDATE pending_content SET ${fields.join(', ')} WHERE id = ?`, values, (err) => {
        if (err) return res.status(500).json({ error: err.message });
        res.json({ success: true });
    });
});

app.post('/api/approve/:id', (req, res) => {
    db.get("SELECT * FROM pending_content WHERE id = ?", [req.params.id], (err, row) => {
        if (err || !row) return res.status(500).json({ error: 'Item not found' });
        
        const title = JSON.parse(row.title);
        const summary = JSON.parse(row.summary);
        const content = JSON.parse(row.content);

        db.serialize(() => {
            db.run(`INSERT INTO published_content (id, type, title, summary, content, image_url) VALUES (?, ?, ?, ?, ?, ?)`,
                [row.id, row.type, row.title, row.summary, row.content, '']); // Image URL generation handled by agent or manual
            db.run(`DELETE FROM pending_content WHERE id = ?`, [req.params.id]);
        });
        res.json({ success: true });
    });
});

app.delete('/api/pending/:id', (req, res) => {
    db.run("DELETE FROM pending_content WHERE id = ?", req.params.id, (err) => {
        if (err) return res.status(500).json({ error: err.message });
        res.json({ success: true });
    });
});

app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});

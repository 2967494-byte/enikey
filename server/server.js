const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

const app = express();
app.set('trust proxy', 1);
const PORT = process.env.PORT || 3000;
const DB_PATH = path.join(__dirname, 'database.sqlite');
const NEWS_UPLOAD_DIR = path.join(__dirname, '..', 'uploads', 'news');
const ADMIN_PASSWORD = process.env.ENIKEY_ADMIN_PASSWORD || '';
const ADMIN_SECRET = process.env.ENIKEY_ADMIN_SECRET || '';
const ADMIN_SESSION_COOKIE = 'enikey_news_session';
const ADMIN_SESSION_TTL = 8 * 60 * 60 * 1000;

const allowedOrigins = (process.env.CORS_ORIGIN || 'http://localhost:5500,http://127.0.0.1:5500,http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080')
    .split(',').map((origin) => origin.trim()).filter(Boolean);
app.use(cors({
    origin: (origin, callback) => callback(null, !origin || allowedOrigins.includes(origin)),
    credentials: true
}));
app.use(express.json({ limit: '7mb' }));
fs.mkdirSync(NEWS_UPLOAD_DIR, { recursive: true });
app.use('/uploads/news', express.static(NEWS_UPLOAD_DIR, { maxAge: '7d', immutable: true }));

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

    db.run(`CREATE TABLE IF NOT EXISTS news_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title_ru TEXT NOT NULL,
        title_en TEXT NOT NULL DEFAULT '',
        summary_ru TEXT NOT NULL DEFAULT '',
        summary_en TEXT NOT NULL DEFAULT '',
        content_ru TEXT NOT NULL,
        content_en TEXT NOT NULL DEFAULT '',
        image_url TEXT NOT NULL DEFAULT '',
        is_published INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        publication_date TEXT NOT NULL DEFAULT ''
    )`);

    // Совместимость с базами, созданными до появления даты публикации.
    db.run(`ALTER TABLE news_posts ADD COLUMN publication_date TEXT NOT NULL DEFAULT ''`, (err) => {
        if (err && !/duplicate column name/i.test(err.message)) console.error('News date migration error:', err);
    });
});

function signAdminSession(payload) {
    return crypto.createHmac('sha256', ADMIN_SECRET).update(payload).digest('base64url');
}

function getAdminSession(req) {
    if (!ADMIN_SECRET) return false;
    const cookie = req.headers.cookie || '';
    const entry = cookie.split(';').map((part) => part.trim()).find((part) => part.startsWith(`${ADMIN_SESSION_COOKIE}=`));
    if (!entry) return false;
    let value;
    try {
        value = decodeURIComponent(entry.slice(ADMIN_SESSION_COOKIE.length + 1));
    } catch (error) {
        return false;
    }
    const [payload, signature] = value.split('.');
    if (!payload || !signature) return false;
    const expected = signAdminSession(payload);
    const providedBuffer = Buffer.from(signature);
    const expectedBuffer = Buffer.from(expected);
    if (providedBuffer.length !== expectedBuffer.length || !crypto.timingSafeEqual(providedBuffer, expectedBuffer)) return false;
    try {
        const session = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
        return Number.isFinite(session.expiresAt) && session.expiresAt > Date.now();
    } catch (error) {
        return false;
    }
}

function requireAdmin(req, res, next) {
    if (!getAdminSession(req)) return res.status(401).json({ error: 'Требуется вход администратора' });
    next();
}

function sameOriginForAdmin(req, res, next) {
    const origin = req.get('origin');
    if (origin) {
        try {
            if (new URL(origin).host !== req.get('host') && !allowedOrigins.includes(origin)) {
                return res.status(403).json({ error: 'Запрос с другого сайта запрещён' });
            }
        } catch (error) {
            return res.status(403).json({ error: 'Некорректный источник запроса' });
        }
    }
    next();
}

const loginAttempts = new Map();
function limitLoginAttempts(req, res, next) {
    const key = req.ip || req.socket.remoteAddress || 'unknown';
    const now = Date.now();
    const attempt = loginAttempts.get(key);
    if (attempt && attempt.blockedUntil > now) {
        return res.status(429).json({ error: 'Слишком много попыток. Попробуйте позже.' });
    }
    if (!attempt || attempt.windowStartedAt < now - 15 * 60 * 1000) {
        loginAttempts.set(key, { count: 0, windowStartedAt: now, blockedUntil: 0 });
    }
    req.loginAttemptKey = key;
    next();
}

function newsRowToJson(row) {
    return {
        id: row.id,
        title: { ru: row.title_ru, en: row.title_en || row.title_ru },
        summary: { ru: row.summary_ru, en: row.summary_en || row.summary_ru },
        content: { ru: row.content_ru, en: row.content_en || row.content_ru },
        imageUrl: row.image_url || '',
        isPublished: Boolean(row.is_published),
        createdAt: row.publication_date ? `${row.publication_date} 12:00:00` : row.created_at,
        publicationDate: row.publication_date || String(row.created_at || '').slice(0, 10),
        updatedAt: row.updated_at
    };
}

function newsListRowToJson(row) {
    return {
        id: row.id,
        title: { ru: row.title_ru, en: row.title_en || row.title_ru },
        summary: { ru: row.summary_ru, en: row.summary_en || row.summary_ru },
        imageUrl: row.image_url || '',
        isPublished: Boolean(row.is_published),
        createdAt: row.publication_date ? `${row.publication_date} 12:00:00` : row.created_at,
        publicationDate: row.publication_date || String(row.created_at || '').slice(0, 10)
    };
}

function getPublishedNews(callback) {
    db.all(`SELECT id, title_ru, title_en, summary_ru, summary_en, image_url, is_published, created_at, publication_date
        FROM news_posts WHERE is_published = 1
        ORDER BY COALESCE(NULLIF(publication_date, ''), substr(created_at, 1, 10)) DESC, created_at DESC, id DESC`, [], callback);
}

function cleanNewsInput(body) {
    const value = body || {};
    return {
        titleRu: String(value.titleRu || '').trim().slice(0, 220),
        titleEn: String(value.titleEn || '').trim().slice(0, 220),
        summaryRu: String(value.summaryRu || '').trim().slice(0, 360),
        summaryEn: String(value.summaryEn || '').trim().slice(0, 360),
        contentRu: String(value.contentRu || '').trim().slice(0, 100000),
        contentEn: String(value.contentEn || '').trim().slice(0, 100000),
        publicationDate: String(value.publicationDate || '').trim().slice(0, 10),
        imageUrl: String(value.imageUrl || '').trim().slice(0, 500),
        isPublished: value.isPublished === true
    };
}

function validateNewsInput(value) {
    if (!value.titleRu || !value.contentRu) return 'Заполните заголовок и текст на русском языке';
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value.publicationDate)) return 'Укажите дату публикации';
    const parsedDate = new Date(`${value.publicationDate}T00:00:00.000Z`);
    if (!Number.isFinite(parsedDate.getTime()) || parsedDate.toISOString().slice(0, 10) !== value.publicationDate) return 'Укажите корректную дату публикации';
    if (value.imageUrl && !/^\/uploads\/news\/[a-zA-Z0-9_-]+\.(?:jpg|png|webp)$/.test(value.imageUrl)) {
        return 'Изображение должно быть загружено через форму';
    }
    return '';
}

function ensurePublicationDateAvailable(date, exceptId, callback) {
    const checkForConflict = () => {
        const sql = `SELECT id FROM news_posts
            WHERE COALESCE(NULLIF(publication_date, ''), substr(created_at, 1, 10)) = ?
            AND (? IS NULL OR id != ?) LIMIT 1`;
        db.get(sql, [date, exceptId, exceptId], (err, row) => {
            if (err) return callback(err);
            callback(row ? false : null);
        });
    };

    if (exceptId === null) return checkForConflict();
    db.get(`SELECT COALESCE(NULLIF(publication_date, ''), substr(created_at, 1, 10)) AS date
        FROM news_posts WHERE id = ?`, [exceptId], (err, row) => {
        if (err) return callback(err);
        if (row && row.date === date) return callback(null);
        checkForConflict();
    });
}

app.get('/api/news', (req, res) => {
    getPublishedNews((err, rows) => {
        if (err) return res.status(500).json({ error: 'Не удалось загрузить новости' });
        res.json(rows.map(newsListRowToJson));
    });
});

app.get('/api/news/:id', (req, res) => {
    db.get('SELECT * FROM news_posts WHERE id = ? AND is_published = 1', [req.params.id], (err, row) => {
        if (err) return res.status(500).json({ error: 'Не удалось загрузить публикацию' });
        if (!row) return res.status(404).json({ error: 'Публикация не найдена' });
        res.json(newsRowToJson(row));
    });
});

app.post('/api/admin/login', sameOriginForAdmin, limitLoginAttempts, (req, res) => {
    if (!ADMIN_PASSWORD || !ADMIN_SECRET) {
        return res.status(503).json({ error: 'Админка не настроена. Задайте ENIKEY_ADMIN_PASSWORD и ENIKEY_ADMIN_SECRET на сервере.' });
    }
    const provided = Buffer.from(String(req.body && req.body.password || ''));
    const expected = Buffer.from(ADMIN_PASSWORD);
    const valid = provided.length === expected.length && crypto.timingSafeEqual(provided, expected);
    const attempt = loginAttempts.get(req.loginAttemptKey);
    if (!valid) {
        attempt.count += 1;
        if (attempt.count >= 5) attempt.blockedUntil = Date.now() + 15 * 60 * 1000;
        return res.status(401).json({ error: 'Неверный пароль' });
    }
    loginAttempts.delete(req.loginAttemptKey);
    const payload = Buffer.from(JSON.stringify({ expiresAt: Date.now() + ADMIN_SESSION_TTL })).toString('base64url');
    const signature = signAdminSession(payload);
    const isHttps = req.secure || req.headers['x-forwarded-proto'] === 'https';
    res.cookie(ADMIN_SESSION_COOKIE, `${payload}.${signature}`, {
        httpOnly: true,
        sameSite: 'lax',
        secure: isHttps,
        maxAge: ADMIN_SESSION_TTL,
        path: '/'
    });
    res.json({ success: true });
});

app.get('/api/admin/session', (req, res) => {
    res.json({ authenticated: getAdminSession(req) });
});

app.post('/api/admin/logout', sameOriginForAdmin, (req, res) => {
    const isHttps = req.secure || req.headers['x-forwarded-proto'] === 'https';
    res.clearCookie(ADMIN_SESSION_COOKIE, {
        httpOnly: true,
        sameSite: 'lax',
        secure: isHttps,
        path: '/'
    });
    res.json({ success: true });
});

app.get('/api/admin/news', requireAdmin, (req, res) => {
    db.all(`SELECT * FROM news_posts ORDER BY COALESCE(NULLIF(publication_date, ''), substr(created_at, 1, 10)) DESC, created_at DESC, id DESC`, [], (err, rows) => {
        if (err) return res.status(500).json({ error: 'Не удалось загрузить публикации' });
        res.json(rows.map(newsRowToJson));
    });
});

app.post('/api/admin/upload', sameOriginForAdmin, requireAdmin, (req, res) => {
    const dataUrl = String(req.body && req.body.imageData || '');
    const match = dataUrl.match(/^data:image\/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)$/);
    if (!match) return res.status(400).json({ error: 'Загрузите изображение JPG, PNG или WebP' });
    const buffer = Buffer.from(match[2], 'base64');
    if (!buffer.length || buffer.length > 5 * 1024 * 1024) return res.status(400).json({ error: 'Размер изображения — до 5 МБ' });
    const signatures = {
        jpeg: buffer.length > 3 && buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff,
        png: buffer.length > 8 && buffer.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])),
        webp: buffer.length > 12 && buffer.toString('ascii', 0, 4) === 'RIFF' && buffer.toString('ascii', 8, 12) === 'WEBP'
    };
    if (!signatures[match[1]]) return res.status(400).json({ error: 'Файл не соответствует формату изображения' });
    const extension = match[1] === 'jpeg' ? 'jpg' : match[1];
    const filename = `${crypto.randomUUID()}.${extension}`;
    fs.writeFile(path.join(NEWS_UPLOAD_DIR, filename), buffer, (err) => {
        if (err) return res.status(500).json({ error: 'Не удалось сохранить изображение' });
        res.json({ imageUrl: `/uploads/news/${filename}` });
    });
});

app.post('/api/admin/news', sameOriginForAdmin, requireAdmin, (req, res) => {
    const article = cleanNewsInput(req.body);
    const validationError = validateNewsInput(article);
    if (validationError) return res.status(400).json({ error: validationError });
    const sql = `INSERT INTO news_posts
        (title_ru, title_en, summary_ru, summary_en, content_ru, content_en, image_url, is_published, publication_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`;
    ensurePublicationDateAvailable(article.publicationDate, null, (dateError) => {
        if (dateError) return res.status(500).json({ error: 'Не удалось проверить дату публикации' });
        if (dateError === false) return res.status(409).json({ error: 'На эту дату уже есть публикация. Выберите другой день.' });
        db.run(sql, [article.titleRu, article.titleEn, article.summaryRu, article.summaryEn,
            article.contentRu, article.contentEn, article.imageUrl, article.isPublished ? 1 : 0, article.publicationDate], function(err) {
        if (err) return res.status(500).json({ error: 'Не удалось сохранить публикацию' });
        db.get('SELECT * FROM news_posts WHERE id = ?', [this.lastID], (selectErr, row) => {
            if (selectErr) return res.status(500).json({ error: 'Публикация сохранена, но её не удалось загрузить' });
            res.status(201).json(newsRowToJson(row));
        });
        });
    });
});

app.put('/api/admin/news/:id', sameOriginForAdmin, requireAdmin, (req, res) => {
    const article = cleanNewsInput(req.body);
    const validationError = validateNewsInput(article);
    if (validationError) return res.status(400).json({ error: validationError });
    const sql = `UPDATE news_posts SET title_ru = ?, title_en = ?, summary_ru = ?, summary_en = ?,
        content_ru = ?, content_en = ?, image_url = ?, is_published = ?, publication_date = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?`;
    ensurePublicationDateAvailable(article.publicationDate, req.params.id, (dateError) => {
        if (dateError) return res.status(500).json({ error: 'Не удалось проверить дату публикации' });
        if (dateError === false) return res.status(409).json({ error: 'На эту дату уже есть публикация. Выберите другой день.' });
        db.run(sql, [article.titleRu, article.titleEn, article.summaryRu, article.summaryEn,
            article.contentRu, article.contentEn, article.imageUrl, article.isPublished ? 1 : 0, article.publicationDate, req.params.id], function(err) {
        if (err) return res.status(500).json({ error: 'Не удалось обновить публикацию' });
        if (!this.changes) return res.status(404).json({ error: 'Публикация не найдена' });
        db.get('SELECT * FROM news_posts WHERE id = ?', [req.params.id], (selectErr, row) => {
            if (selectErr) return res.status(500).json({ error: 'Публикация обновлена, но её не удалось загрузить' });
            res.json(newsRowToJson(row));
        });
        });
    });
});

app.delete('/api/admin/news/:id', sameOriginForAdmin, requireAdmin, (req, res) => {
    db.get('SELECT image_url FROM news_posts WHERE id = ?', [req.params.id], (selectErr, row) => {
        if (selectErr) return res.status(500).json({ error: 'Не удалось найти публикацию' });
        if (!row) return res.status(404).json({ error: 'Публикация не найдена' });
        db.run('DELETE FROM news_posts WHERE id = ?', [req.params.id], function(deleteErr) {
            if (deleteErr) return res.status(500).json({ error: 'Не удалось удалить публикацию' });
            const filename = path.basename(row.image_url || '');
            if (filename) {
                db.get('SELECT COUNT(*) AS count FROM news_posts WHERE image_url = ?', [row.image_url], (countErr, countRow) => {
                    if (!countErr && countRow.count === 0) fs.unlink(path.join(NEWS_UPLOAD_DIR, filename), () => {});
                });
            }
            res.json({ success: true });
        });
    });
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

const https = require('https');

app.post('/api/translate', (req, res) => {
    db.get("SELECT settings FROM agent_config WHERE id = 1", [], (err, row) => {
        if (err || !row) return res.status(500).json({ error: 'AI Config not set' });
        
        const config = JSON.parse(row.settings);
        const { data, langs } = req.body;

        const prompt = `Translate this JSON tech content from Russian to ${langs.join(' and ')}. Keep HTML tags. Return ONLY JSON with keys for each language. Content: ${JSON.stringify(data)}`;

        // OpenAI payload
        const payload = JSON.stringify({
            model: "gpt-3.5-turbo",
            messages: [{ role: "user", content: prompt }],
            temperature: 0.3
        });

        const options = {
            hostname: 'api.openai.com',
            path: '/v1/chat/completions',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${config.key}`
            }
        };

        const aiReq = https.request(options, (aiRes) => {
            let responseBody = '';
            aiRes.on('data', (chunk) => responseBody += chunk);
            aiRes.on('end', () => {
                try {
                    const result = JSON.parse(responseBody);
                    const contentStr = result.choices[0].message.content;
                    const jsonMatch = contentStr.match(/\{[\s\S]*\}/);
                    res.json(JSON.parse(jsonMatch ? jsonMatch[0] : contentStr));
                } catch (e) {
                    res.status(500).json({ error: 'AI Parse Error: ' + responseBody });
                }
            });
        });

        aiReq.on('error', (e) => res.status(500).json({ error: e.message }));
        aiReq.write(payload);
        aiReq.end();
    });
});

app.post('/api/generate', (req, res) => {
    db.get("SELECT settings FROM agent_config WHERE id = 1", [], (err, row) => {
        if (err || !row) return res.status(500).json({ error: 'AI Config not set' });
        
        const config = JSON.parse(row.settings);
        const { task } = req.body;

        const prompt = `You are an AI Content Creator for 'Enikey Pulse' tech agency. 
        Task: ${task.prompt}
        Type: ${task.type}
        Generate a professional draft in Russian, English, and Chinese. 
        Return ONLY valid JSON with this structure:
        {
          "title": { "ru": "...", "en": "...", "zh": "..." },
          "excerpt": { "ru": "...", "en": "...", "zh": "..." },
          "content": { "ru": "...", "en": "...", "zh": "..." },
          "image": "agency_tech_abstract.png"
        }`;

        const payload = JSON.stringify({
            model: "gpt-3.5-turbo",
            messages: [{ role: "system", content: "You output only JSON." }, { role: "user", content: prompt }],
            temperature: 0.7
        });

        const options = {
            hostname: 'api.openai.com',
            path: '/v1/chat/completions',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${config.key}`
            }
        };

        const aiReq = https.request(options, (aiRes) => {
            let responseBody = '';
            aiRes.on('data', (chunk) => responseBody += chunk);
            aiRes.on('end', () => {
                try {
                    const result = JSON.parse(responseBody);
                    const contentStr = result.choices[0].message.content;
                    const jsonMatch = contentStr.match(/\{[\s\S]*\}/);
                    const draftData = JSON.parse(jsonMatch ? jsonMatch[0] : contentStr);
                    
                    // Формируем финальный объект для очереди
                    const draft = {
                        id: Date.now().toString(),
                        type: task.type,
                        status: 'pending',
                        title: draftData.title,
                        summary: draftData.excerpt,
                        content: draftData.content,
                        image: draftData.image || 'agency_tech_abstract.png'
                    };
                    res.json(draft);
                } catch (e) {
                    res.status(500).json({ error: 'AI Generation Error: ' + responseBody });
                }
            });
        });

        aiReq.on('error', (e) => res.status(500).json({ error: e.message }));
        aiReq.write(payload);
        aiReq.end();
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

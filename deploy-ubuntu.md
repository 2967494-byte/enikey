# Развертывание Enikey Pulse на Ubuntu VPS

Эта инструкция поможет вам развернуть проект Enikey Pulse (фронтенд + локальный Node.js бэкенд с SQLite) на чистом сервере с установленной ОС Ubuntu (рекомендуется 20.04 LTS или 22.04 LTS).

## Шаг 1: Подключение к серверу и обновление пакетов

Подключитесь к вашему серверу по SSH:
```bash
ssh root@IP_ВАШЕГО_СЕРВЕРА
```

Обновите списки пакетов и установите базовые утилиты:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install curl git build-essential nano -y
```

## Шаг 2: Установка Node.js и npm

Мы будем использовать NodeSource для установки актуальной версии Node.js (рекомендуется 20.x).

```bash
# Загрузка скрипта установки
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -

# Установка Node.js
sudo apt install -y nodejs

# Проверка установки
node -v
npm -v
```

## Шаг 3: Загрузка проекта на сервер (из GitHub)

Создайте директорию в `/var/www/`, затем клонируйте ваш репозиторий с GitHub.

```bash
# Создание директории для всех веб-проектов (если еще нет)
sudo mkdir -p /var/www/
cd /var/www/

# Клонирование репозитория (замените URL на ссылку вашего репозитория)
sudo git clone https://github.com/ВАШ_АККАУНТ/enikey.git

# Настройка прав, чтобы вы могли работать с файлами сервера:
sudo chown -R $USER:$USER /var/www/enikey
```

*(Если репозиторий приватный, вам потребуется предварительно создать и добавить на GitHub SSH-ключ, либо использовать Personal Access Token при `git clone`).*

Перейдите в директорию сервера:
```bash
cd /var/www/enikey/server
```

## Шаг 4: Установка зависимостей бэкенда

Находясь в папке `/server`, установите необходимые модули (express, sqlite3, cors):

```bash
npm install
```

## Шаг 5: Настройка PM2 (Менеджер процессов)

Чтобы Node.js сервер работал постоянно (в фоне) и автоматически перезапускался после перезагрузки ОС, установим PM2.

```bash
# Глобальная установка PM2
sudo npm install pm2 -g

# Запуск сервера
pm2 start server.js --name "enikey-api"

# Сохранение списка процессов для автозагрузки
pm2 save
pm2 startup
```
*Выполните команду, которую выдаст `pm2 startup`, чтобы добавить PM2 в автозагрузку системы.*

## Шаг 6: Установка и настройка Nginx (Веб-сервер)

Nginx будет отдавать статические файлы (фронтенд) и перенаправлять API запросы на Node.js сервер.

```bash
sudo apt install nginx -y
```

Создайте конфигурационный файл для вашего сайта:
```bash
sudo nano /etc/nginx/sites-available/enikey
```

Вставьте следующую конфигурацию (замените `ВАШ_ДОМЕН_ИЛИ_IP` на реальное значение):

```nginx
server {
    listen 80;
    server_name ВАШ_ДОМЕН_ИЛИ_IP;

    root /var/www/enikey;
    index index.html;

    # Раздача статики (фронтенд)
    location / {
        try_files $uri $uri/ =404;
    }

    # Проксирование запросов к API
    location /api/ {
        proxy_pass http://localhost:3000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```
*Сохраните файл (Ctrl+O, Enter) и закройте редактор (Ctrl+X).*

Активируйте конфигурацию и перезапустите Nginx:
```bash
# Создание симлинка
sudo ln -s /etc/nginx/sites-available/enikey /etc/nginx/sites-enabled/

# Удаление дефолтного конфига
sudo rm /etc/nginx/sites-enabled/default

# Проверка конфигурации на ошибки
sudo nginx -t

# Перезапуск Nginx
sudo systemctl restart nginx
```

## Шаг 7: Конфигурация фронтенда

Убедитесь, что ваш файл `/var/www/enikey/api-config.js` настроен на относительные пути или правильный IP, чтобы запросы шли через Nginx:

```javascript
window.API_CONFIG = {
    // В продакшене лучше использовать относительный путь:
    BASE_URL: '/api'
};
```
Если вы меняете `api-config.js`, никаких других действий не требуется — пользователи автоматически начнут использовать новый маршрут.

## Шаг 8: Настройка фаервола (UFW)

Откройте порты для HTTP, HTTPS и SSH (если UFW включен):

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

---

**Готово!** 🎉 
Ваша платформа Enikey Pulse теперь успешно развернута на сервере Ubuntu. 
- Фронтенд доступен по вашему IP или домену.
- API запросы маршрутизируются сервером Nginx на внутренний Node.js процесс.
- Все данные безопасно сохраняются в локальной базе `database.sqlite`.

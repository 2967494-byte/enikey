const localHosts = ['localhost', '127.0.0.1'];
const isLocal = localHosts.includes(window.location.hostname);

const API_CONFIG = {
    BASE_URL: isLocal ? `${window.location.protocol}//${window.location.hostname}:3000/api` : '/api',
    ENABLED: true
};

window.API_CONFIG = API_CONFIG;

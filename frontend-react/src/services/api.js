import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});

// Separate instance with long timeout for long-running operations (optimization)
export const apiLong = axios.create({
  baseURL: API_BASE_URL,
  timeout: 900000, // 15 minutes
  headers: { 'Content-Type': 'application/json' },
});

const AUTH_TOKEN_KEY = 'smi_auth_token';

const requestInterceptor = (config) => {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
};

api.interceptors.request.use(requestInterceptor);
apiLong.interceptors.request.use(requestInterceptor);

const responseInterceptor = (response) => response.data;
const errorInterceptor = (error) => {
  const message = error.response?.data?.detail || error.message || 'An error occurred';
  console.error('API Error:', message);
  if (error.response?.status === 401) {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem('smi_auth_username');
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
  }
  return Promise.reject({ message, status: error.response?.status });
};

api.interceptors.response.use(responseInterceptor, errorInterceptor);
apiLong.interceptors.response.use(responseInterceptor, errorInterceptor);

export default api;

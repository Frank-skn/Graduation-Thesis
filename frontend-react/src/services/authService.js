import api from './api';

const AUTH_TOKEN_KEY = 'smi_auth_token';
const AUTH_USERNAME_KEY = 'smi_auth_username';

const authService = {
  login: async (username, password) => {
    // api interceptor unwraps response.data → trả về { access_token, token_type, username }
    const res = await api.post('/auth/login', { username, password });
    localStorage.setItem(AUTH_TOKEN_KEY, res.access_token);
    localStorage.setItem(AUTH_USERNAME_KEY, res.username);
    return res;
  },
  logout: () => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USERNAME_KEY);
  },
  getToken: () => localStorage.getItem(AUTH_TOKEN_KEY),
  getUsername: () => localStorage.getItem(AUTH_USERNAME_KEY),
  isAuthenticated: () => !!localStorage.getItem(AUTH_TOKEN_KEY),
};

export default authService;

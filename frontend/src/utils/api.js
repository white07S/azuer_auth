import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include session token if available
apiClient.interceptors.request.use(
  (config) => {
    const sessionId = localStorage.getItem('sessionId');
    if (sessionId) {
      config.headers['X-Session-ID'] = sessionId;
    }
    const accessToken = localStorage.getItem('accessToken');
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor to handle common errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Unauthorized - clear session and redirect to login
      localStorage.removeItem('sessionId');
      localStorage.removeItem('accessToken');
      window.location.reload();
    }
    return Promise.reject(error);
  }
);

// Authentication API
export const authAPI = {
  // Start authentication flow
  startAuth: async (clientId = null) => {
    try {
      const response = await apiClient.post('/api/auth/start', {
        client_id: clientId,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to start auth:', error);
      throw error;
    }
  },

  // Check authentication status
  checkAuthStatus: async (sessionId) => {
    try {
      const response = await apiClient.get(`/api/auth/status/${sessionId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to check auth status:', error);
      throw error;
    }
  },

  // Complete authentication
  completeAuth: async (sessionId) => {
    try {
      const response = await apiClient.post('/api/auth/complete', {
        session_id: sessionId,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to complete auth:', error);
      throw error;
    }
  },

  // Refresh token
  refreshToken: async (sessionId) => {
    try {
      const response = await apiClient.post(`/api/auth/refresh/${sessionId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to refresh token:', error);
      throw error;
    }
  },

  // Logout
  logout: async (sessionId) => {
    try {
      const response = await apiClient.post(`/api/auth/logout/${sessionId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to logout:', error);
      throw error;
    }
  },

  // Get session info
  getSessionInfo: async (sessionId) => {
    try {
      const response = await apiClient.get(`/api/session/${sessionId}/info`);
      return response.data;
    } catch (error) {
      console.error('Failed to get session info:', error);
      return null;
    }
  },

  // Check if token needs refresh
  checkTokenExpiry: async (sessionId) => {
    try {
      const info = await authAPI.getSessionInfo(sessionId);
      if (!info || !info.token_expires_at) {
        return { needsRefresh: true, sessionInfo: info };
      }

      const expiryTime = new Date(info.token_expires_at);
      const now = new Date();
      const bufferMinutes = 5;
      const bufferTime = new Date(now.getTime() + bufferMinutes * 60000);

      return { needsRefresh: bufferTime >= expiryTime, sessionInfo: info };
    } catch (error) {
      console.error('Failed to check token expiry:', error);
      return { needsRefresh: true, sessionInfo: null };
    }
  },
};

// Chat API
export const chatAPI = {
  // Send a chat message
  sendMessage: async (sessionId, message, context = null) => {
    try {
      const response = await apiClient.post('/api/chat/message', {
        session_id: sessionId,
        message: message,
        context: context,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to send message:', error);
      throw error;
    }
  },

  // Get chat history
  getChatHistory: async (sessionId, limit = 50) => {
    try {
      const response = await apiClient.get(`/api/chat/history/${sessionId}`, {
        params: { limit },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to get chat history:', error);
      return [];
    }
  },

  // Clear chat history
  clearChatHistory: async (sessionId) => {
    try {
      const response = await apiClient.delete(`/api/chat/history/${sessionId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to clear chat history:', error);
      throw error;
    }
  },
};

// Health check
export const healthCheck = async () => {
  try {
    const response = await apiClient.get('/api/health');
    return response.data;
  } catch (error) {
    console.error('Health check failed:', error);
    return null;
  }
};

// Export the API client for advanced usage
export default apiClient;

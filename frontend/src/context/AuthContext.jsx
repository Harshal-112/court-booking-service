
import {
  createContext,
  useContext,
  useEffect,
  useState,
} from 'react';

import { api, ApiError } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(
    () => localStorage.getItem('access_token')
  );

  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const isAuthenticated = Boolean(token);

  useEffect(() => {
    let active = true;

    const restoreSession = async () => {
      if (!token) {
        setUser(null);
        setLoading(false);
        return;
      }

      setLoading(true);

      try {
        const profile = await api.get('/auth/me');

        if (active) {
          setUser(profile);
        }
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          localStorage.removeItem('access_token');

          if (active) {
            setToken(null);
            setUser(null);
          }
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    restoreSession();

    return () => {
      active = false;
    };
  }, [token]);

  const establishSession = async (authRequest) => {
    setLoading(true);

    try {
      const data = await authRequest();

      localStorage.setItem('access_token', data.access_token);

      const profile = await api.get('/auth/me');

      setToken(data.access_token);
      setUser(profile);

      return { ...data, user: profile };
    } catch (error) {
      localStorage.removeItem('access_token');
      setToken(null);
      setUser(null);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const login = (credentials) =>
    establishSession(() => api.login(credentials));

  const register = (userData) =>
    establishSession(() => api.register(userData));

  const logout = () => {
    localStorage.removeItem('access_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        loading,
        isAuthenticated,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }

  return context;
}

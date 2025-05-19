import { createContext, useContext, useState, useEffect } from 'react';
import { Magic } from 'magic-sdk';
import { useRouter } from 'next/router';
import axios from 'axios';

// Define the auth context type
type AuthContextType = {
  user: any;
  isLoading: boolean;
  isAuthenticated: boolean;
  userRoles: string[];
  login: (email: string) => Promise<void>;
  logout: () => Promise<void>;
  checkUserRole: (requiredRole: string) => boolean;
};

// Create the auth context with default values
const AuthContext = createContext<AuthContextType>({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  userRoles: [],
  login: async () => {},
  logout: async () => {},
  checkUserRole: () => false,
});

// Magic instance
let magic: any;

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [userRoles, setUserRoles] = useState<string[]>([]);
  const router = useRouter();

  // Initialize Magic when component mounts
  useEffect(() => {
    if (typeof window !== 'undefined') {
      magic = new Magic(process.env.NEXT_PUBLIC_MAGIC_PUBLISHABLE_KEY as string);
      checkUserLoggedIn();
    }
  }, []);

  // Check if user is logged in
  const checkUserLoggedIn = async () => {
    try {
      setIsLoading(true);
      
      // Check if user is logged in with Magic
      const isLoggedIn = await magic.user.isLoggedIn();
      
      if (isLoggedIn) {
        // Get user data
        const userData = await magic.user.getMetadata();
        setUser(userData);
        
        // Fetch user roles from API
        const response = await axios.get('/api/auth/roles');
        setUserRoles(response.data.roles || []);
      }
    } catch (error) {
      console.error('Error checking authentication:', error);
      setUser(null);
      setUserRoles([]);
    } finally {
      setIsLoading(false);
    }
  };

  // Login with Magic Link
  const login = async (email: string) => {
    try {
      setIsLoading(true);
      
      // Send magic link to user's email
      await magic.auth.loginWithMagicLink({ email });
      
      // Get user data after successful login
      const userData = await magic.user.getMetadata();
      setUser(userData);
      
      // Fetch user roles from API
      const response = await axios.get('/api/auth/roles');
      setUserRoles(response.data.roles || []);
      
      // Redirect to dashboard after login
      router.push('/dev/dashboard');
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  // Logout
  const logout = async () => {
    try {
      setIsLoading(true);
      
      // Logout from Magic
      await magic.user.logout();
      
      // Clear user data
      setUser(null);
      setUserRoles([]);
      
      // Redirect to login page
      router.push('/dev/login');
    } catch (error) {
      console.error('Logout error:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  // Check if user has required role
  const checkUserRole = (requiredRole: string) => {
    return userRoles.includes(requiredRole);
  };

  // Auth context value
  const value = {
    user,
    isLoading,
    isAuthenticated: !!user,
    userRoles,
    login,
    logout,
    checkUserRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// Custom hook to use auth context
export const useAuth = () => useContext(AuthContext);

// HOC to protect routes
export const withAuth = (Component: React.ComponentType<any>, requiredRole?: string) => {
  const AuthenticatedComponent = (props: any) => {
    const { isAuthenticated, isLoading, checkUserRole } = useAuth();
    const router = useRouter();

    useEffect(() => {
      if (!isLoading && !isAuthenticated) {
        router.push('/dev/login');
      }

      if (!isLoading && isAuthenticated && requiredRole && !checkUserRole(requiredRole)) {
        router.push('/dev/unauthorized');
      }
    }, [isLoading, isAuthenticated, router]);

    if (isLoading) {
      return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
    }

    if (!isAuthenticated) {
      return null;
    }

    if (requiredRole && !checkUserRole(requiredRole)) {
      return null;
    }

    return <Component {...props} />;
  };

  return AuthenticatedComponent;
};

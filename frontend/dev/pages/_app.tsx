import { useEffect } from 'react';
import { useRouter } from 'next/router';
import { useAuth } from '../contexts/AuthContext';
import type { AppProps } from 'next/app';
import '../styles/globals.css';
import { Toaster } from 'react-hot-toast';

function MyApp({ Component, pageProps }: AppProps) {
  const { isLoading } = useAuth();
  const router = useRouter();

  // Global loading state
  if (isLoading && router.pathname !== '/dev/login') {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="font-sans">
      <Toaster position="top-right" />
      <Component {...pageProps} />
    </div>
  );
}

export default function App(props: AppProps) {
  return (
    <AuthProvider>
      <MyApp {...props} />
    </AuthProvider>
  );
}

import { AuthProvider } from '../contexts/AuthContext';

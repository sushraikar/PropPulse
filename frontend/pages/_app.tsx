import { AppProps } from 'next/app';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import { appWithTranslation } from 'next-i18next';
import { QueryClient, QueryClientProvider } from 'react-query';
import { useState } from 'react';
import '../styles/globals.css';
import { AuthProvider } from '../contexts/AuthContext';

// Create a client
const queryClient = new QueryClient();

// Create theme with RTL support
const getDirection = (locale: string) => {
  return locale === 'ar' ? 'rtl' : 'ltr';
};

function MyApp({ Component, pageProps, router }: AppProps) {
  const [darkMode, setDarkMode] = useState(false);
  const locale = router.locale || 'en';
  const dir = getDirection(locale);

  const theme = createTheme({
    direction: dir,
    palette: {
      mode: darkMode ? 'dark' : 'light',
      primary: {
        main: '#2E5BFF',
      },
      secondary: {
        main: '#FF6B2E',
      },
    },
    typography: {
      fontFamily: 'Inter, Roboto, "Helvetica Neue", Arial, sans-serif',
    },
  });

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <div dir={dir}>
            <Component {...pageProps} toggleDarkMode={() => setDarkMode(!darkMode)} />
          </div>
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default appWithTranslation(MyApp);

import { StrictMode, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from '@/contexts/authContext';
import { AppInitializer } from '@/components/common/AppInitializer';
import { AuthFallback } from '@/components/common/AuthFallback';
import { App } from '@/App';
import '@/index.css';

const queryClient = new QueryClient();

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Suspense fallback={<AuthFallback />}>
            <AppInitializer>
              <App />
            </AppInitializer>
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
      <Toaster
        toastOptions={{
          style: {
            background: 'var(--card)',
            color: 'var(--card-foreground)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            boxShadow: '0 4px 16px -4px oklch(0 0 0 / 12%)',
            fontSize: '0.875rem',
            padding: '0.625rem 0.875rem',
          },
          success: { iconTheme: { primary: 'var(--primary)', secondary: 'var(--primary-foreground)' } },
          error: { iconTheme: { primary: 'var(--destructive)', secondary: 'white' } },
        }}
      />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </StrictMode>,
);

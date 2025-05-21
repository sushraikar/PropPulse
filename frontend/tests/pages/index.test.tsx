import { render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import Dashboard from '../../pages/index'; // Adjust path as necessary
import '@testing-library/jest-dom';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock next-i18next
jest.mock('next-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
  serverSideTranslations: jest.fn().mockResolvedValue({}),
}));

// Mock next/router (optional, enable if needed)
// jest.mock('next/router', () => ({
//   useRouter: () => ({
//     route: '/',
//     pathname: '',
//     query: '',
//     asPath: '',
//     push: jest.fn(),
//     events: {
//       on: jest.fn(),
//       off: jest.fn(),
//     },
//     beforePopState: jest.fn(() => null),
//     prefetch: jest.fn(() => null),
//   }),
// }));

// Set up NEXT_PUBLIC_API_URL
process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000/api';

describe('Dashboard Page', () => {
  beforeEach(() => {
    // Clear all previous mock calls and implementations
    mockedAxios.get.mockReset();
  });

  test('renders loading states initially', () => {
    render(<Dashboard />);
    expect(screen.getByText('dashboard.loadingProperties')).toBeInTheDocument();
    expect(screen.getByText('dashboard.loadingProposals')).toBeInTheDocument();
  });

  test('fetches and displays properties and proposals successfully', async () => {
    const mockProperties = [{ id: 'PROP_001', name: 'Test Property', developer: 'Test Dev', price: 100000, yield: 5.0, currency: 'AED' }];
    const mockProposals = [{ id: 'prop_test1', date: '2023-01-01', properties_count: 1, status: 'completed' }];

    mockedAxios.get.mockImplementation((url: string) => {
      if (url.includes('/properties')) {
        return Promise.resolve({ data: mockProperties });
      }
      if (url.includes('/proposals')) {
        return Promise.resolve({ data: mockProposals });
      }
      return Promise.reject(new Error('not found'));
    });
    
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Test Property')).toBeInTheDocument();
      expect(screen.getByText((content, element) => content.startsWith('dashboard.proposalId') && content.includes('prop_test1'))).toBeInTheDocument();
    });

    expect(screen.queryByText('dashboard.loadingProperties')).not.toBeInTheDocument();
    expect(screen.queryByText('dashboard.loadingProposals')).not.toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument(); // Properties count
    expect(screen.getByText('1')).toBeInTheDocument(); // Proposals count
  });

  test('displays error message if properties fetch fails', async () => {
    const mockProposals = [{ id: 'prop_test1', date: '2023-01-01', properties_count: 1, status: 'completed' }];
    
    mockedAxios.get.mockImplementation((url: string) => {
      if (url.includes('/properties')) {
        return Promise.reject(new Error('Failed to fetch properties'));
      }
      if (url.includes('/proposals')) {
        return Promise.resolve({ data: mockProposals });
      }
      return Promise.reject(new Error('not found'));
    });

    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Failed to fetch properties')).toBeInTheDocument();
    });
    
    // Check that proposals are still loaded or loading
    await waitFor(() => {
        expect(screen.getByText((content, element) => content.startsWith('dashboard.proposalId') && content.includes('prop_test1'))).toBeInTheDocument();
    });
    expect(screen.queryByText('dashboard.loadingProposals')).not.toBeInTheDocument();
  });

  test('displays error message if proposals fetch fails', async () => {
    const mockProperties = [{ id: 'PROP_001', name: 'Test Property', developer: 'Test Dev', price: 100000, yield: 5.0, currency: 'AED' }];

    mockedAxios.get.mockImplementation((url: string) => {
      if (url.includes('/properties')) {
        return Promise.resolve({ data: mockProperties });
      }
      if (url.includes('/proposals')) {
        return Promise.reject(new Error('Failed to fetch proposals'));
      }
      return Promise.reject(new Error('not found'));
    });

    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Failed to fetch proposals')).toBeInTheDocument();
    });

    // Check that properties are still loaded
    await waitFor(() => {
      expect(screen.getByText('Test Property')).toBeInTheDocument();
    });
    expect(screen.queryByText('dashboard.loadingProperties')).not.toBeInTheDocument();
  });
});

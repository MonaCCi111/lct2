export const apiConfig = {
  baseUrl: (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, ''),
  enableMocks: import.meta.env.VITE_ENABLE_MOCKS === 'true',
};

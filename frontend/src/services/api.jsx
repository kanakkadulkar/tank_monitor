import axios from 'axios';

// Vite uses import.meta.env instead of process.env
// Also, the variable must start with VITE_ to be accessible
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:5001';

const api = axios.create({ 
  baseURL: BASE, 
  timeout: 8000 
});

export const getLatest      = ()  => api.get('/latest').then(r => r.data);
export const getAnalysis    = ()  => api.get('/analysis').then(r => r.data);
export const getHourly      = ()  => api.get('/hourly').then(r => r.data);
export const getBuffer      = ()  => api.get('/buffer').then(r => r.data);
export const getAnomalies   = (n) => api.get(`/anomalies?limit=${n || 50}`).then(r => r.data);
export const getFlowSummary = ()  => api.get('/flow_summary').then(r => r.data);
export const postCollect    = (d) => api.post('/collect', d).then(r => r.data);

// Report opens in a new tab (returns HTML, not JSON)
export const REPORT_URL = `${BASE}/report`;
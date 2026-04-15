import axios from 'axios';

// Vite uses import.meta.env instead of process.env
// Also, the variable must start with VITE_ to be accessible
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:5001';

const api = axios.create({ 
  baseURL: BASE, 
  timeout: 8000 
});

export const getLatest   = ()  => api.get('/latest').then(r => r.data);
export const getAnalysis = ()  => api.get('/analysis').then(r => r.data);
export const getForecast = ()  => api.get('/forecast').then(r => r.data);
export const getHourly   = ()  => api.get('/hourly').then(r => r.data);
export const getBuffer   = ()  => api.get('/buffer').then(r => r.data);
export const postCollect = (d) => api.post('/collect', d).then(r => r.data);
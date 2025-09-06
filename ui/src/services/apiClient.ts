import axios from 'axios';
import { API_BASE } from '../utils/constants';

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 20000,
  withCredentials: true
});

api.interceptors.response.use(r => r, err => {
  console.error('API error', err); // lightweight
  return Promise.reject(err);
});

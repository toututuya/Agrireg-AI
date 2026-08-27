import axios from 'axios';
import { baseUrl } from '../config/config';

const service = axios.create({
  baseURL: baseUrl,
  timeout: 45000
});

service.interceptors.request.use(config => {
  const token = localStorage.getItem('Authorization');
  if (token) config.headers.Authorization = token;
  return config;
});

export default service;

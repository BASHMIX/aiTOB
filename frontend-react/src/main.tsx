import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

import axios from 'axios'
import { useHubStore } from './store/useHubStore'

// Axios Interceptor for Hub Password
axios.interceptors.request.use((config) => {
  const password = useHubStore.getState().hubPassword;
  console.log(`[AXIOS] Request to ${config.url}, Password set: ${!!password}`);
  if (password) {
    config.headers['Authorization'] = `Bearer ${password}`;
    config.headers['X-Hub-Password'] = password; // Legacy support
  }
  return config;
});


ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

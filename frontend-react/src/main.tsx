import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

import axios from 'axios'

// Authentication is an HttpOnly session cookie. No password or session secret
// is copied into localStorage or JavaScript-managed request headers.
axios.defaults.withCredentials = true;


ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

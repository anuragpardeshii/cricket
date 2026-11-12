import React from 'react';
import ReactDOM from 'react-dom/client';
import { InstallApp } from './components/InstallApp';
import App from './App';
import './styles.css';
import { initializeTheme, ThemeProvider } from './theme/ThemeProvider';

initializeTheme();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider><InstallApp/><App /></ThemeProvider>
  </React.StrictMode>,
);

if ('serviceWorker' in navigator && import.meta.env.PROD) navigator.serviceWorker.register('/sw.js').catch(()=>{});

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { BackendProvider } from './contexts/BackendContext';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BackendProvider url="ws://localhost:8100/ws/live2d">
      <App />
    </BackendProvider>
  </React.StrictMode>,
);

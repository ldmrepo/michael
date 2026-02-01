/**
 * Telegram Mini App Entry Point
 *
 * Initializes the Mini App and renders A2UI components.
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';

// Initialize Telegram Web App
declare global {
  interface Window {
    Telegram: {
      WebApp: {
        ready: () => void;
        expand: () => void;
        close: () => void;
        sendData: (data: string) => void;
        MainButton: {
          text: string;
          color: string;
          textColor: string;
          isVisible: boolean;
          isActive: boolean;
          show: () => void;
          hide: () => void;
          onClick: (callback: () => void) => void;
          offClick: (callback: () => void) => void;
          enable: () => void;
          disable: () => void;
        };
        BackButton: {
          isVisible: boolean;
          show: () => void;
          hide: () => void;
          onClick: (callback: () => void) => void;
          offClick: (callback: () => void) => void;
        };
        themeParams: {
          bg_color?: string;
          text_color?: string;
          hint_color?: string;
          link_color?: string;
          button_color?: string;
          button_text_color?: string;
          secondary_bg_color?: string;
        };
        colorScheme: 'light' | 'dark';
        initData: string;
        initDataUnsafe: {
          user?: {
            id: number;
            first_name: string;
            last_name?: string;
            username?: string;
            language_code?: string;
          };
          query_id?: string;
          start_param?: string;
        };
      };
    };
  }
}

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('root');
  if (!root) return;

  // Check if running in Telegram
  const tg = window.Telegram?.WebApp;
  if (!tg) {
    root.innerHTML = '<div class="error">이 앱은 Telegram 내에서만 사용할 수 있습니다.</div>';
    return;
  }

  // Initialize Telegram Web App
  tg.ready();
  tg.expand();

  // Render React app
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
});

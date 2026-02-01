/**
 * Main App Component
 *
 * Fetches A2UI surface from session and renders it.
 */

import { useState, useEffect, useCallback } from 'react';
import { A2UIRenderer } from './components/A2UIRenderer';
import type { SurfaceUpdate, Action } from './types';

interface AppState {
  loading: boolean;
  error: string | null;
  surface: SurfaceUpdate | null;
  dataModel: Record<string, unknown>;
}

export function App() {
  const [state, setState] = useState<AppState>({
    loading: true,
    error: null,
    surface: null,
    dataModel: {},
  });

  const tg = window.Telegram.WebApp;

  // Get session ID from URL
  const sessionId = new URLSearchParams(window.location.search).get('session');

  // Fetch initial state
  useEffect(() => {
    if (!sessionId) {
      // No session ID - show demo surface
      setState({
        loading: false,
        error: null,
        surface: getDemoSurface(),
        dataModel: {},
      });
      return;
    }

    fetchSession();
  }, [sessionId]);

  const fetchSession = async () => {
    try {
      // In production, this would be a WebSocket or API call to Gateway
      // For now, we simulate with a placeholder
      const response = await fetch(`/api/webapp/session/${sessionId}`, {
        headers: {
          'X-Telegram-Init-Data': tg.initData,
        },
      });

      if (!response.ok) {
        throw new Error('세션을 불러올 수 없습니다.');
      }

      const data = await response.json();
      setState({
        loading: false,
        error: null,
        surface: data.surface,
        dataModel: data.dataModel || {},
      });
    } catch (error) {
      // Development fallback - show demo surface
      setState({
        loading: false,
        error: null,
        surface: getDemoSurface(),
        dataModel: {},
      });
    }
  };

  // Handle action from A2UI component
  const handleAction = useCallback(
    (action: Action) => {
      console.log('Action triggered:', action);

      // Build result with action and current data model
      const result = {
        action: action.name,
        context: action.context,
        data: state.dataModel,
      };

      // Send data back to Telegram and close
      tg.sendData(JSON.stringify(result));
      tg.close();
    },
    [state.dataModel, tg]
  );

  // Handle data model update from form inputs
  const handleDataUpdate = useCallback((path: string, value: unknown) => {
    setState((prev) => {
      const newDataModel = { ...prev.dataModel };
      setNestedValue(newDataModel, path, value);
      return { ...prev, dataModel: newDataModel };
    });
  }, []);

  // Setup back button
  useEffect(() => {
    tg.BackButton.show();
    const handleBack = () => {
      tg.close();
    };
    tg.BackButton.onClick(handleBack);
    return () => tg.BackButton.offClick(handleBack);
  }, [tg]);

  if (state.loading) {
    return <div className="loading">로딩 중...</div>;
  }

  if (state.error) {
    return <div className="error">{state.error}</div>;
  }

  if (!state.surface) {
    return <div className="error">표시할 내용이 없습니다.</div>;
  }

  return (
    <div className="app">
      <A2UIRenderer
        surface={state.surface}
        dataModel={state.dataModel}
        onAction={handleAction}
        onDataUpdate={handleDataUpdate}
        theme={tg.colorScheme}
      />
    </div>
  );
}

// Helper: Set nested value in object
function setNestedValue(obj: Record<string, unknown>, path: string, value: unknown) {
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  const parts = cleanPath.split('/');
  let current: Record<string, unknown> = obj;

  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i];
    if (!(part in current) || typeof current[part] !== 'object') {
      current[part] = {};
    }
    current = current[part] as Record<string, unknown>;
  }

  current[parts[parts.length - 1]] = value;
}

// Demo surface for development
function getDemoSurface(): SurfaceUpdate {
  return {
    type: 'surfaceUpdate',
    surfaceId: 'main',
    components: [
      {
        id: 'title',
        component: {
          Text: {
            text: { literalString: '예약 정보 입력' },
            usageHint: 'h1',
          },
        },
      },
      {
        id: 'name-input',
        component: {
          TextField: {
            label: { literalString: '이름' },
            value: { path: '/form/name' },
            placeholder: { literalString: '이름을 입력하세요' },
            required: true,
          },
        },
      },
      {
        id: 'date-input',
        component: {
          DateTimeInput: {
            label: { literalString: '날짜' },
            value: { path: '/form/date' },
            mode: 'date',
            required: true,
          },
        },
      },
      {
        id: 'submit-btn',
        component: {
          Button: {
            label: { literalString: '제출' },
            action: { name: 'submit_form' },
            variant: 'primary',
          },
        },
      },
    ],
  };
}

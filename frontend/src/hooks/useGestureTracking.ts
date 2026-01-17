import { useState, useEffect, useRef } from 'react';

export interface HandData {
  x: number;
  y: number;
  state: 'OPEN' | 'CLOSED' | 'UNKNOWN';
  definitive: boolean;
  confidence: number | null;
  score: number;
}

export interface GestureData {
  timestamp: number;
  screen_size: {
    width: number;
    height: number;
  };
  hand: HandData | null;
}

export function useGestureTracking() {
  const [gestureData, setGestureData] = useState<GestureData | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const previousStateRef = useRef<'OPEN' | 'CLOSED' | 'UNKNOWN'>('UNKNOWN');

  useEffect(() => {
    // Check if electron API is available
    if (typeof window === 'undefined' || !window.electron) {
      console.warn('Electron API not available');
      return;
    }

    console.log('[HOOK] Setting up gesture data listener');

    // Listen for gesture data from main process
    const unsubscribe = window.electron.on('gesture-data', (data: GestureData) => {
      console.log('[HOOK] Received gesture data:', data);
      setGestureData(data);
      setIsConnected(true);
    });

    // Note: Gesture tracking starts automatically in main process
    // No need to request it manually

    return () => {
      console.log('[HOOK] Cleaning up gesture listener');
      unsubscribe();
      // Don't stop gesture tracking - let it continue running
      // The main process will handle cleanup when the app closes
    };
  }, []);

  // Detect state transitions (edge detection)
  const previousState = previousStateRef.current;
  const currentState = gestureData?.hand?.state || 'UNKNOWN';
  
  useEffect(() => {
    previousStateRef.current = currentState;
  }, [currentState]);

  const didTransitionToClose = previousState === 'OPEN' && currentState === 'CLOSED';
  const didTransitionToOpen = previousState === 'CLOSED' && currentState === 'OPEN';

  return {
    gestureData,
    isConnected,
    hand: gestureData?.hand || null,
    didTransitionToClose,
    didTransitionToOpen,
  };
}

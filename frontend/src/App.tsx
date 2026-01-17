import './App.css'
import Time from './widgets/Time'
import Weather from './widgets/Weather'
import Cursor from './components/Cursor'
import { useGestureTracking } from './hooks/useGestureTracking'
import { useEffect } from 'react'

function App() {
  const { hand, isConnected } = useGestureTracking()
  
  useEffect(() => {
    console.log('[APP] Mounted - checking window.electron:', !!window.electron);
  }, []);
  
  useEffect(() => {
    console.log('[APP] Connection status:', isConnected);
  }, [isConnected]);

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      backgroundColor: '#000',
      position: 'relative'
    }}>
      {/* Connection status indicator */}
      <div style={{
        position: 'fixed',
        top: 10,
        left: 10,
        color: isConnected ? '#0f0' : '#f00',
        fontSize: '12px',
        zIndex: 10000,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        padding: '4px 8px',
        borderRadius: '4px'
      }}>
        {isConnected ? '● Gesture Tracking Active' : '● Gesture Tracking Offline'}
      </div>

      {/* Debug info */}
      {hand && (
        <div style={{
          position: 'fixed',
          top: 10,
          right: 10,
          color: '#fff',
          fontSize: '11px',
          zIndex: 10000,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          padding: '6px 10px',
          borderRadius: '4px',
          fontFamily: 'monospace'
        }}>
          <div>State: <span style={{ 
            color: hand.state === 'CLOSED' ? '#0f0' : hand.state === 'OPEN' ? '#f00' : '#888' 
          }}>{hand.state}</span></div>
          <div>Position: {Math.round(hand.x)}, {Math.round(hand.y)}</div>
          <div>Score: {hand.score.toFixed(2)}</div>
          <div>Definitive: {hand.definitive ? 'Yes' : 'No'}</div>
        </div>
      )}

      {/* Gesture Cursor */}
      {hand && (
        <Cursor 
          x={hand.x} 
          y={hand.y} 
          size={hand.state === 'CLOSED' ? 20 : 30}
          state={hand.state}
        />
      )}

      {/* Widgets with gesture support */}
      <Time 
        gestureX={hand?.x}
        gestureY={hand?.y}
        gestureState={hand?.state}
        gestureDefinitive={hand?.definitive}
      />
      <Weather 
        gestureX={hand?.x}
        gestureY={hand?.y}
        gestureState={hand?.state}
        gestureDefinitive={hand?.definitive}
      />
    </div>
  )
}

export default App

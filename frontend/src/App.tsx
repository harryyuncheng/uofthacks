import './App.css'
import Time from './widgets/Time'
import Weather from './widgets/Weather'
import Calendar from './widgets/Calendar'
import VoiceOrb from './widgets/VoiceOrb'
import Cursor from './components/Cursor'
import AudioBorder from './components/AudioBorder'
import { useGestureTracking } from './hooks/useGestureTracking'
import { useEffect, useState, useCallback } from 'react'


interface WidgetPosition {
  id: string
  x: number
  y: number
  width: number
  height: number
}

function App() {
  const { hand, isConnected } = useGestureTracking()
  const [widgetPositions, setWidgetPositions] = useState<Map<string, WidgetPosition>>(new Map())
  
  useEffect(() => {
    console.log('[APP] Mounted - checking window.electron:', !!window.electron);
  }, []);
  
  useEffect(() => {
    console.log('[APP] Connection status:', isConnected);
  }, [isConnected]);

  const updateWidgetPosition = useCallback((id: string, position: WidgetPosition) => {
    setWidgetPositions(prev => {
      const updated = new Map(prev)
      updated.set(id, position)
      return updated
    })
  }, [])

  const getOtherWidgets = useCallback((id: string) => {
    const widgets: WidgetPosition[] = []
    for (const [otherId, pos] of widgetPositions) {
      if (otherId !== id) {
        widgets.push(pos)
      }
    }
    return widgets
  }, [widgetPositions])

const checkCollision = useCallback((id: string, x: number, y: number, width: number, height: number): { x: number, y: number } => {
    let adjustedX = x
    let adjustedY = y

    for (const [otherId, otherPos] of widgetPositions) {
      if (otherId === id) continue

      // Calculate bounding boxes with no padding
      const padding = 0
      const left = adjustedX - width / 2 - padding
      const right = adjustedX + width / 2 + padding
      const top = adjustedY - height / 2 - padding
      const bottom = adjustedY + height / 2 + padding

      const otherLeft = otherPos.x - otherPos.width / 2 - padding
      const otherRight = otherPos.x + otherPos.width / 2 + padding
      const otherTop = otherPos.y - otherPos.height / 2 - padding
      const otherBottom = otherPos.y + otherPos.height / 2 + padding

      // Check for overlap
      const overlapsX = left < otherRight && right > otherLeft
      const overlapsY = top < otherBottom && bottom > otherTop

      if (overlapsX && overlapsY) {
        // Calculate overlap amounts
        const overlapLeft = otherRight - left
        const overlapRight = right - otherLeft
        const overlapTop = otherBottom - top
        const overlapBottom = bottom - otherTop

        // Find minimum overlap direction to push the widget
        const minOverlap = Math.min(overlapLeft, overlapRight, overlapTop, overlapBottom)

        if (minOverlap === overlapLeft) {
          adjustedX = otherRight + width / 2 + padding
        } else if (minOverlap === overlapRight) {
          adjustedX = otherLeft - width / 2 - padding
        } else if (minOverlap === overlapTop) {
          adjustedY = otherBottom + height / 2 + padding
        } else {
          adjustedY = otherTop - height / 2 - padding
        }
      }
    }

    return { x: adjustedX, y: adjustedY }
  }, [widgetPositions])

  return (
    <AudioBorder>
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
        id="time-widget"
        gestureX={hand?.x}
        gestureY={hand?.y}
        gestureState={hand?.state}
        gestureDefinitive={hand?.definitive}
        onPositionUpdate={updateWidgetPosition}
        checkCollision={checkCollision}
        getOtherWidgets={getOtherWidgets}
      />
      <Weather 
        id="weather-widget"
        gestureX={hand?.x}
        gestureY={hand?.y}
        gestureState={hand?.state}
        gestureDefinitive={hand?.definitive}
        onPositionUpdate={updateWidgetPosition}
        checkCollision={checkCollision}
        getOtherWidgets={getOtherWidgets}
      />
      <Calendar 
        id="calendar-widget"
        gestureX={hand?.x}
        gestureY={hand?.y}
        gestureState={hand?.state}
        gestureDefinitive={hand?.definitive}
        onPositionUpdate={updateWidgetPosition}
        checkCollision={checkCollision}
        getOtherWidgets={getOtherWidgets}
      />
      <VoiceOrb 
        id="orb"
        gestureX={hand.x}
        gestureY={hand.y}
        gestureState={hand.state}
        gestureDefinitive={hand.definitive}
        onPositionUpdate={updateWidgetPosition}
        checkCollision={checkCollision}
        getOtherWidgets={getOtherWidgets}
      />
    </div>
  )
}

export default App

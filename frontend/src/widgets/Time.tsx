import { useState, useEffect } from 'react'
import DraggableWidget from '../components/Widget'

interface TimeProps {
  id: string
  gestureX?: number
  gestureY?: number
  gestureState?: 'OPEN' | 'CLOSED' | 'UNKNOWN'
  gestureDefinitive?: boolean
  onPositionUpdate?: (id: string, position: { id: string, x: number, y: number, width: number, height: number }) => void
  checkCollision?: (id: string, x: number, y: number, width: number, height: number) => { x: number, y: number }
  getOtherWidgets?: (id: string) => Array<{ id: string, x: number, y: number, width: number, height: number }>
}

function Time({ id, gestureX, gestureY, gestureState, gestureDefinitive, onPositionUpdate, checkCollision, getOtherWidgets }: TimeProps) {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date())
    }, 1000)

    return () => clearInterval(timer)
  }, [])

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    })
  }

  return (
    <DraggableWidget
      id={id}
      initialX={window.innerWidth / 2}
      initialY={40}
      gestureX={gestureX}
      gestureY={gestureY}
      gestureState={gestureState}
      gestureDefinitive={gestureDefinitive}
      onPositionUpdate={onPositionUpdate}
      checkCollision={checkCollision}
      getOtherWidgets={getOtherWidgets}
      style={{
        color: 'white',
        fontSize: '24px',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        fontWeight: '300',
        whiteSpace: 'nowrap',
        width: 'auto',
        height: '20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}
    >
      {formatTime(time)}
    </DraggableWidget>
  )
}

export default Time

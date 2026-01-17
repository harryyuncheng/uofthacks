import { useState, useEffect } from 'react'
import DraggableWidget from '../components/Widget'

function Time() {
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
      second: '2-digit',
      hour12: true
    })
  }

  return (
    <DraggableWidget
      initialX={window.innerWidth / 2}
      initialY={40}
      style={{
        color: 'white',
        fontSize: '48px',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        fontWeight: '300',
        whiteSpace: 'nowrap'
      }}
    >
      {formatTime(time)}
    </DraggableWidget>
  )
}

export default Time

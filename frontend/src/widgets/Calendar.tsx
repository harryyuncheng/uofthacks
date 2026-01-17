import { useState, useEffect } from 'react'
import DraggableWidget from '../components/Widget'

interface CalendarProps {
  id: string
  gestureX?: number
  gestureY?: number
  gestureState?: 'OPEN' | 'CLOSED' | 'UNKNOWN'
  gestureDefinitive?: boolean
  onPositionUpdate?: (id: string, position: { id: string, x: number, y: number, width: number, height: number }) => void
  checkCollision?: (id: string, x: number, y: number, width: number, height: number) => { x: number, y: number }
  getOtherWidgets?: (id: string) => Array<{ id: string, x: number, y: number, width: number, height: number }>
}

interface CalendarEvent {
  id: string
  title: string
  startTime: Date
  endTime: Date
  color: string
  location?: string
}

function Calendar({ id, gestureX, gestureY, gestureState, gestureDefinitive, onPositionUpdate, checkCollision, getOtherWidgets }: CalendarProps) {
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [currentTime, setCurrentTime] = useState(new Date())

  useEffect(() => {
    // Generate dummy events for today
    const today = new Date()
    const dummyEvents: CalendarEvent[] = [
      {
        id: '1',
        title: 'Morning Standup',
        startTime: new Date(today.getFullYear(), today.getMonth(), today.getDate(), 9, 0),
        endTime: new Date(today.getFullYear(), today.getMonth(), today.getDate(), 9, 30),
        color: '#3b82f6',
        location: 'E7 2070'
      },
      {
        id: '2',
        title: 'Design Review',
        startTime: new Date(today.getFullYear(), today.getMonth(), today.getDate(), 11, 0),
        endTime: new Date(today.getFullYear(), today.getMonth(), today.getDate(), 12, 0),
        color: '#8b5cf6',
        location: 'DC 1302'
      },
      {
        id: '3',
        title: 'Lunch with Team',
        startTime: new Date(today.getFullYear(), today.getMonth(), today.getDate(), 12, 30),
        endTime: new Date(today.getFullYear(), today.getMonth(), today.getDate(), 13, 30),
        color: '#10b981',
        location: 'SLC Great Hall'
      },
      {
        id: '4',
        title: 'Client Meeting',
        startTime: new Date(today.getFullYear(), today.getMonth(), today.getDate(), 14, 0),
        endTime: new Date(today.getFullYear(), today.getMonth(), today.getDate(), 15, 30),
        color: '#f59e0b',
        location: 'E5 6004'
      },
      {
        id: '5',
        title: 'Code Review Session',
        startTime: new Date(today.getFullYear(), today.getMonth(), today.getDate(), 16, 0),
        endTime: new Date(today.getFullYear(), today.getMonth(), today.getDate(), 17, 0),
        color: '#ef4444',
        location: 'MC 3003'
      }
    ]

    setEvents(dummyEvents)

    // Update current time every minute
    const timer = setInterval(() => {
      setCurrentTime(new Date())
    }, 60000)

    return () => clearInterval(timer)
  }, [])

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    })
  }

  const isEventNow = (event: CalendarEvent) => {
    return currentTime >= event.startTime && currentTime <= event.endTime
  }

  const isEventUpcoming = (event: CalendarEvent) => {
    return currentTime < event.startTime
  }

  const getNextEvents = () => {
    const now = currentTime
    return events
      .filter(event => event.endTime > now)
      .sort((a, b) => a.startTime.getTime() - b.startTime.getTime())
      .slice(0, 4) // Show next 4 events
  }

  const nextEvents = getNextEvents()

  return (
    <DraggableWidget
      id={id}
      initialX={window.innerWidth / 2}
      initialY={200}
      gestureX={gestureX}
      gestureY={gestureY}
      gestureState={gestureState}
      gestureDefinitive={gestureDefinitive}
      onPositionUpdate={onPositionUpdate}
      checkCollision={checkCollision}
      getOtherWidgets={getOtherWidgets}
      style={{
        color: 'white',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        backdropFilter: 'blur(10px)',
        borderRadius: '16px',
        padding: '8px 8px',
        width: '200px',
        height: 'auto',
        maxHeight: '500px',
        overflowY: 'auto',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)'
      }}
    >
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}>

        {/* Events List */}
        {nextEvents.length > 0 ? (
          nextEvents.map(event => {
            const isNow = isEventNow(event)
            const isUpcoming = isEventUpcoming(event)

            return (
              <div
                key={event.id}
                style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0px',
                    padding: '8px 10px',
                  backgroundColor: `${event.color}25`,
                  borderRadius: '8px',
                  borderLeft: `4px solid ${event.color}`,
                  position: 'relative',
                  transition: 'background-color 0.2s'
                }}
              >
                {/* Title */}
                <div style={{
                  fontSize: '15px',
                  fontWeight: '600',
                  color: '#fff'
                }}>
                  {event.title}
                </div>

                {/* Location (left) and Time/NOW (right) on same line */}
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginTop: '4px',
                  gap: '8px'
                }}>
                  <div style={{
                    fontSize: '13px',
                    color: 'rgba(255, 255, 255, 0.8)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    flex: 1,
                    marginRight: '8px'
                  }}>
                    {event.location || ''}
                  </div>

                  <div style={{
                    fontSize: '13px',
                    fontWeight: '500',
                    color: isNow ? '#10b981' : 'rgba(255, 255, 255, 0.7)',
                    flex: '0 0 auto'
                  }}>
                    {isNow ? 'NOW' : formatTime(event.startTime)}
                  </div>
                </div>
              </div>
            )
          })
        ) : (
          <div style={{
            padding: '20px',
            textAlign: 'center',
            color: '#9ca3af',
            fontSize: '14px'
          }}>
            No upcoming events today
          </div>
        )}
      </div>
    </DraggableWidget>
  )
}

export default Calendar

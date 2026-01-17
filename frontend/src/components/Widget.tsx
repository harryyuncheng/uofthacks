import { useState, useEffect, useRef } from 'react'
import type { CSSProperties, ReactNode } from 'react'

interface DraggableWidgetProps {
  initialX?: number
  initialY?: number
  children: ReactNode
  style?: CSSProperties
  gestureX?: number
  gestureY?: number
  gestureState?: 'OPEN' | 'CLOSED' | 'UNKNOWN'
  gestureDefinitive?: boolean
}

function DraggableWidget({ 
  initialX = window.innerWidth / 2, 
  initialY = 40, 
  children,
  style = {},
  gestureX,
  gestureY,
  gestureState,
  gestureDefinitive = false
}: DraggableWidgetProps) {
  const [position, setPosition] = useState({ x: initialX, y: initialY })
  const [isDragging, setIsDragging] = useState(false)
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 })
  const widgetRef = useRef<HTMLDivElement>(null)
  const prevGestureState = useRef<'OPEN' | 'CLOSED' | 'UNKNOWN'>('UNKNOWN')

  // Mouse-based dragging
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        setPosition({
          x: e.clientX - dragOffset.x,
          y: e.clientY - dragOffset.y
        })
      }
    }

    const handleMouseUp = () => {
      setIsDragging(false)
    }

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, dragOffset])

  // Gesture-based dragging
  useEffect(() => {
    if (gestureX === undefined || gestureY === undefined || !gestureState || !gestureDefinitive) {
      return
    }

    const rect = widgetRef.current?.getBoundingClientRect()
    if (!rect) return

    // Check if gesture cursor is over this widget
    const isOver = gestureX >= rect.left && gestureX <= rect.right &&
                   gestureY >= rect.top && gestureY <= rect.bottom

    const prevState = prevGestureState.current
    
    // Detect CLOSED gesture (grab) when hovering - transition from any non-CLOSED state
    if (isOver && gestureState === 'CLOSED' && prevState !== 'CLOSED') {
      // Start gesture drag
      const centerX = rect.left + rect.width / 2
      const centerY = rect.top + rect.height / 2
      setDragOffset({
        x: gestureX - centerX,
        y: gestureY - centerY
      })
      setIsDragging(true)
      console.log('[WIDGET] Started gesture drag');
    }

    // Detect OPEN gesture (release) - transition from CLOSED to OPEN
    if (gestureState === 'OPEN' && prevState === 'CLOSED' && isDragging) {
      setIsDragging(false)
      console.log('[WIDGET] Released gesture drag');
    }

    // Update position while dragging with gesture
    if (isDragging && gestureState === 'CLOSED') {
      setPosition({
        x: gestureX - dragOffset.x,
        y: gestureY - dragOffset.y
      })
    }

    prevGestureState.current = gestureState
  }, [gestureX, gestureY, gestureState, gestureDefinitive, isDragging, dragOffset])

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    setDragOffset({
      x: e.clientX - rect.left - rect.width / 2,
      y: e.clientY - rect.top - rect.height / 2
    })
    setIsDragging(true)
  }

  return (
    <div 
      ref={widgetRef}
      onMouseDown={handleMouseDown}
      style={{
        position: 'absolute',
        left: `${position.x}px`,
        top: `${position.y}px`,
        transform: 'translate(-50%, -50%)',
        padding: '12px 24px',
        cursor: isDragging ? 'grabbing' : 'grab',
        userSelect: 'none',
        ...(isDragging && {
          border: '1px solid #808080',
          borderRadius: '8px'
        }),
        ...style
      }}>
      {children}
    </div>
  )
}

export default DraggableWidget

import { useState, useEffect, useRef } from 'react'
import type { CSSProperties, ReactNode } from 'react'

interface DraggableWidgetProps {
  id: string
  initialX?: number
  initialY?: number
  children: ReactNode
  style?: CSSProperties
  gestureX?: number
  gestureY?: number
  gestureState?: 'OPEN' | 'CLOSED' | 'UNKNOWN'
  gestureDefinitive?: boolean
  onPositionUpdate?: (id: string, position: { id: string, x: number, y: number, width: number, height: number }) => void
  checkCollision?: (id: string, x: number, y: number, width: number, height: number) => { x: number, y: number }
}

function DraggableWidget({ 
  id,
  initialX = window.innerWidth / 2, 
  initialY = 40, 
  children,
  style = {},
  gestureX,
  gestureY,
  gestureState,
  gestureDefinitive = false,
  onPositionUpdate,
  checkCollision
}: DraggableWidgetProps) {
  const [position, setPosition] = useState({ x: initialX, y: initialY })
  const [isDragging, setIsDragging] = useState(false)
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 })
  const widgetRef = useRef<HTMLDivElement>(null)
  const prevGestureState = useRef<'OPEN' | 'CLOSED' | 'UNKNOWN'>('UNKNOWN')

  // Helper function to constrain position within boundaries
  const constrainPosition = (x: number, y: number) => {
    const rect = widgetRef.current?.getBoundingClientRect()
    if (!rect) return { x, y }

    const halfWidth = rect.width / 2
    const halfHeight = rect.height / 2

    let constrainedX = x
    let constrainedY = y

    // Clamp x and y to keep widget fully within viewport
    constrainedX = Math.max(halfWidth, Math.min(window.innerWidth - halfWidth, constrainedX))
    constrainedY = Math.max(halfHeight, Math.min(window.innerHeight - halfHeight, constrainedY))

    // Check for collisions with other widgets
    if (checkCollision) {
      const adjusted = checkCollision(id, constrainedX, constrainedY, rect.width, rect.height)
      constrainedX = adjusted.x
      constrainedY = adjusted.y
      
      // Re-clamp after collision adjustment
      constrainedX = Math.max(halfWidth, Math.min(window.innerWidth - halfWidth, constrainedX))
      constrainedY = Math.max(halfHeight, Math.min(window.innerHeight - halfHeight, constrainedY))
    }

    return { x: constrainedX, y: constrainedY }
  }

  // Mouse-based dragging
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        const newPos = constrainPosition(
          e.clientX - dragOffset.x,
          e.clientY - dragOffset.y
        )
        setPosition(newPos)
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
      const newPos = constrainPosition(
        gestureX - dragOffset.x,
        gestureY - dragOffset.y
      )
      setPosition(newPos)
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

  // Update parent with position changes
  useEffect(() => {
    const rect = widgetRef.current?.getBoundingClientRect()
    if (rect && onPositionUpdate) {
      onPositionUpdate(id, {
        id,
        x: position.x,
        y: position.y,
        width: rect.width,
        height: rect.height
      })
    }
  }, [position, id, onPositionUpdate])

  return (
    <>
      <div 
        ref={widgetRef}
        onMouseDown={handleMouseDown}
        style={{
          position: 'absolute',
          left: `${position.x}px`,
          top: `${position.y}px`,
          padding: '2px 4px', 
          transform: 'translate(-50%, -50%)',
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
    </>
  )
}

export default DraggableWidget

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
  getOtherWidgets?: (id: string) => Array<{ id: string, x: number, y: number, width: number, height: number }>
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
  checkCollision,
  getOtherWidgets
}: DraggableWidgetProps) {
  const [position, setPosition] = useState({ x: initialX, y: initialY })
  const [isDragging, setIsDragging] = useState(false)
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 })
  const [snapLines, setSnapLines] = useState<Array<{ type: 'horizontal' | 'vertical', position: number }>>([])
  const widgetRef = useRef<HTMLDivElement>(null)
  const prevGestureState = useRef<'OPEN' | 'CLOSED' | 'UNKNOWN'>('UNKNOWN')

  // Helper function to apply snapping to other widgets
  const applySnapping = (x: number, y: number, width: number, height: number) => {
    if (!getOtherWidgets || !isDragging) return { x, y, snapLines: [] }

    const snapThreshold = 15 // pixels within which to snap
    const otherWidgets = getOtherWidgets(id)
    
    let snappedX = x
    let snappedY = y
    const activeSnapLines: Array<{ type: 'horizontal' | 'vertical', position: number }> = []

    // Current widget edges and center
    const currentLeft = x - width / 2
    const currentRight = x + width / 2
    const currentTop = y - height / 2
    const currentBottom = y + height / 2
    const currentCenterX = x
    const currentCenterY = y

    // Screen center positions
    const screenCenterX = window.innerWidth / 2
    const screenCenterY = window.innerHeight / 2

    let minXDist = Infinity
    let minYDist = Infinity
    let bestXSnapLine: { type: 'horizontal' | 'vertical', position: number } | null = null
    let bestYSnapLine: { type: 'horizontal' | 'vertical', position: number } | null = null

    // Check snapping to screen center (horizontal)
    const screenCenterXDist = Math.abs(currentCenterX - screenCenterX)
    if (screenCenterXDist < snapThreshold) {
      snappedX = screenCenterX
      minXDist = screenCenterXDist
      bestXSnapLine = { type: 'vertical', position: screenCenterX }
    }

    // Check snapping to screen center (vertical)
    const screenCenterYDist = Math.abs(currentCenterY - screenCenterY)
    if (screenCenterYDist < snapThreshold) {
      snappedY = screenCenterY
      minYDist = screenCenterYDist
      bestYSnapLine = { type: 'horizontal', position: screenCenterY }
    }

    for (const other of otherWidgets) {
      const otherLeft = other.x - other.width / 2
      const otherRight = other.x + other.width / 2
      const otherTop = other.y - other.height / 2
      const otherBottom = other.y + other.height / 2
      const otherCenterX = other.x
      const otherCenterY = other.y

      // Horizontal snapping (vertical lines)
      // Left to left
      const leftToLeftDist = Math.abs(currentLeft - otherLeft)
      if (leftToLeftDist < snapThreshold && leftToLeftDist < minXDist) {
        snappedX = otherLeft + width / 2
        minXDist = leftToLeftDist
        bestXSnapLine = { type: 'vertical', position: otherLeft }
      }

      // Right to right
      const rightToRightDist = Math.abs(currentRight - otherRight)
      if (rightToRightDist < snapThreshold && rightToRightDist < minXDist) {
        snappedX = otherRight - width / 2
        minXDist = rightToRightDist
        bestXSnapLine = { type: 'vertical', position: otherRight }
      }

      // Center to center (horizontal)
      const centerToCenter = Math.abs(currentCenterX - otherCenterX)
      if (centerToCenter < snapThreshold && centerToCenter < minXDist) {
        snappedX = otherCenterX
        minXDist = centerToCenter
        bestXSnapLine = { type: 'vertical', position: otherCenterX }
      }

      // Left to right (current widget's left edge to other widget's right edge)
      const leftToRightDist = Math.abs(currentLeft - otherRight)
      if (leftToRightDist < snapThreshold && leftToRightDist < minXDist) {
        snappedX = otherRight + width / 2  // Position center so left edge touches otherRight
        minXDist = leftToRightDist
        bestXSnapLine = { type: 'vertical', position: otherRight }
      }

      // Right to left (current widget's right edge to other widget's left edge)
      const rightToLeftDist = Math.abs(currentRight - otherLeft)
      if (rightToLeftDist < snapThreshold && rightToLeftDist < minXDist) {
        snappedX = otherLeft - width / 2  // Position center so right edge touches otherLeft
        minXDist = rightToLeftDist
        bestXSnapLine = { type: 'vertical', position: otherLeft }
      }

      // Vertical snapping (horizontal lines)
      // Top to top
      const topToTopDist = Math.abs(currentTop - otherTop)
      if (topToTopDist < snapThreshold && topToTopDist < minYDist) {
        snappedY = otherTop + height / 2
        minYDist = topToTopDist
        bestYSnapLine = { type: 'horizontal', position: otherTop }
      }

      // Bottom to bottom
      const bottomToBottomDist = Math.abs(currentBottom - otherBottom)
      if (bottomToBottomDist < snapThreshold && bottomToBottomDist < minYDist) {
        snappedY = otherBottom - height / 2
        minYDist = bottomToBottomDist
        bestYSnapLine = { type: 'horizontal', position: otherBottom }
      }

      // Center to center (vertical)
      const centerToCenterY = Math.abs(currentCenterY - otherCenterY)
      if (centerToCenterY < snapThreshold && centerToCenterY < minYDist) {
        snappedY = otherCenterY
        minYDist = centerToCenterY
        bestYSnapLine = { type: 'horizontal', position: otherCenterY }
      }

      // Top to bottom (current widget's top edge to other widget's bottom edge)
      const topToBottomDist = Math.abs(currentTop - otherBottom)
      if (topToBottomDist < snapThreshold && topToBottomDist < minYDist) {
        snappedY = otherBottom + height / 2  // Position center so top edge touches otherBottom
        minYDist = topToBottomDist
        bestYSnapLine = { type: 'horizontal', position: otherBottom }
      }

      // Bottom to top (current widget's bottom edge to other widget's top edge)
      const bottomToTopDist = Math.abs(currentBottom - otherTop)
      if (bottomToTopDist < snapThreshold && bottomToTopDist < minYDist) {
        snappedY = otherTop - height / 2  // Position center so bottom edge touches otherTop
        minYDist = bottomToTopDist
        bestYSnapLine = { type: 'horizontal', position: otherTop }
      }
    }

    // Only add the snap lines that are actually being used
    if (bestXSnapLine) activeSnapLines.push(bestXSnapLine)
    if (bestYSnapLine) activeSnapLines.push(bestYSnapLine)

    return { x: snappedX, y: snappedY, snapLines: activeSnapLines }
  }

  // Helper function to constrain position within boundaries
  const constrainPosition = (x: number, y: number) => {
    const rect = widgetRef.current?.getBoundingClientRect()
    if (!rect) return { x, y }

    const halfWidth = rect.width / 2
    const halfHeight = rect.height / 2

    // Apply snapping first
    const snapped = applySnapping(x, y, rect.width, rect.height)
    let constrainedX = snapped.x
    let constrainedY = snapped.y

    // Update snap lines visualization
    setSnapLines(snapped.snapLines)

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
      setSnapLines([])
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
      {/* Snap guide lines */}
      {isDragging && snapLines.map((line, idx) => (
        <div
          key={idx}
          style={{
            position: 'fixed',
            ...(line.type === 'vertical' ? {
              left: `${line.position}px`,
              top: 0,
              bottom: 0,
              width: '1px',
            } : {
              top: `${line.position}px`,
              left: 0,
              right: 0,
              height: '1px',
            }),
            backgroundColor: '#808080',
            opacity: 0.5,
            pointerEvents: 'none',
            zIndex: 9999
          }}
        />
      ))}

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

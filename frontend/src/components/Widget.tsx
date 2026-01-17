import { useState, useEffect, CSSProperties, ReactNode } from 'react'

interface DraggableWidgetProps {
  initialX?: number
  initialY?: number
  children: ReactNode
  style?: CSSProperties
}

function DraggableWidget({ 
  initialX = window.innerWidth / 2, 
  initialY = 40, 
  children,
  style = {}
}: DraggableWidgetProps) {
  const [position, setPosition] = useState({ x: initialX, y: initialY })
  const [isDragging, setIsDragging] = useState(false)
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 })

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

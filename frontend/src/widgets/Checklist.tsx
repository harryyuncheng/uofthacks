import { useState, useEffect } from 'react'
import DraggableWidget from '../components/Widget'

interface ChecklistProps {
  id: string
  gestureX?: number
  gestureY?: number
  gestureState?: 'OPEN' | 'CLOSED' | 'UNKNOWN'
  gestureDefinitive?: boolean
  onPositionUpdate?: (id: string, position: { id: string, x: number, y: number, width: number, height: number }) => void
  checkCollision?: (id: string, x: number, y: number, width: number, height: number) => { x: number, y: number }
}

interface TodoItem {
  id: string
  text: string
  completed: boolean
}

function Checklist({ id, gestureX, gestureY, gestureState, gestureDefinitive, onPositionUpdate, checkCollision }: ChecklistProps) {
  const [todos, setTodos] = useState<TodoItem[]>([])

  useEffect(() => {
    if (window.electron) {
      const cleanup = window.electron.on('voice-data', (data: any) => {
        if (data.status === 'goals_updated' && Array.isArray(data.goals)) {
          console.log('[Checklist] Received new goals:', data.goals);
          
          setTodos(prev => {
            const newItems: TodoItem[] = data.goals.map((g: string) => ({
              id: Date.now().toString() + Math.random().toString(),
              text: g,
              completed: false
            }));
            return [...prev, ...newItems];
          });
        }
      });
      return cleanup;
    }
  }, []);

  const toggleTodo = (todoId: string) => {
    setTodos(todos.map(todo => 
      todo.id === todoId ? { ...todo, completed: !todo.completed } : todo
    ))
  }

  // Prevent drag when interacting with form elements
  const stopPropagation = (e: React.MouseEvent) => {
    e.stopPropagation()
  }

  return (
    <DraggableWidget
      id={id}
      initialX={300} // Position explicitly to the left to avoid center stack
      initialY={200}
      gestureX={gestureX}
      gestureY={gestureY}
      gestureState={gestureState}
      gestureDefinitive={gestureDefinitive}
      onPositionUpdate={onPositionUpdate}
      checkCollision={checkCollision}
      style={{
        zIndex: 100
      }}
    >
      <div style={{
        backgroundColor: 'transparent',
        backdropFilter: 'blur(10px)',
        borderRadius: '16px',
        padding: '4px',
        color: 'white',
        width: '200px',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
      }}>
        <h3 style={{ margin: '0 0 12px 0', fontSize: '18px', fontWeight: 600, textAlign: 'right' }}>Goals</h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '200px', overflowY: 'auto' }}>
          {todos.map(todo => (
            <div 
              key={todo.id}
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                alignItems: 'center',
                gap: '8px',
                opacity: todo.completed ? 0.5 : 1
              }}
            >
              <span 
                style={{ 
                  textDecoration: todo.completed ? 'line-through' : 'none',
                  fontSize: '14px',
                  textAlign: 'right'
                }}
              >
                {todo.text}
              </span>
              <input
                type="checkbox"
                checked={todo.completed}
                onChange={() => toggleTodo(todo.id)}
                onMouseDown={stopPropagation}
                style={{
                  cursor: 'pointer',
                  width: '16px',
                  height: '16px',
                  opacity: 0.6
                }}
              />
            </div>
          ))}
          {todos.length === 0 && (
            <div style={{ color: '#888', fontSize: '12px', fontStyle: 'italic', textAlign: 'center' }}>
              No goals yet
            </div>
          )}
        </div>
      </div>
    </DraggableWidget>
  )
}

export default Checklist

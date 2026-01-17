import './App.css'
import Time from './widgets/Time'
import Weather from './widgets/Weather'

function App() {
  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      backgroundColor: '#000',
      position: 'relative'
    }}>
      <Time />
      <Weather />
    </div>
  )
}

export default App

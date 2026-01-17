import { useState, useEffect } from 'react'
import DraggableWidget from '../components/Widget'

interface WeatherProps {
  id: string
  gestureX?: number
  gestureY?: number
  gestureState?: 'OPEN' | 'CLOSED' | 'UNKNOWN'
  gestureDefinitive?: boolean
  onPositionUpdate?: (id: string, position: { id: string, x: number, y: number, width: number, height: number }) => void
  checkCollision?: (id: string, x: number, y: number, width: number, height: number) => { x: number, y: number }
  getOtherWidgets?: (id: string) => Array<{ id: string, x: number, y: number, width: number, height: number }>
}

interface WeatherData {
  temp: number
  condition: string
  location: string
  icon: string
}

function Weather({ id, gestureX, gestureY, gestureState, gestureDefinitive, onPositionUpdate, checkCollision, getOtherWidgets }: WeatherProps) {
  const [weather, setWeather] = useState<WeatherData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchWeather = async () => {
      try {
        // Get location from IP address (faster, no permission needed)
        const locationResponse = await fetch('https://ipapi.co/json/')
        const locationData = await locationResponse.json()
        
        const latitude = locationData.latitude
        const longitude = locationData.longitude
        const city = locationData.city
        
        // Using Open-Meteo API (free, no API key required)
        const weatherResponse = await fetch(
          `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,weather_code&temperature_unit=celsius&timezone=auto`
        )
        const weatherData = await weatherResponse.json()
        
        const weatherCode = weatherData.current.weather_code
        const condition = getWeatherCondition(weatherCode)
        const icon = getWeatherIcon(weatherCode)
        
        setWeather({
          temp: Math.round(weatherData.current.temperature_2m),
          condition,
          location: city || 'Unknown',
          icon
        })
        setLoading(false)
      } catch (err) {
        setError('Failed to fetch weather')
        setLoading(false)
      }
    }

    fetchWeather()
    // Refresh weather every 10 minutes
    const interval = setInterval(fetchWeather, 600000)
    return () => clearInterval(interval)
  }, [])

  const getWeatherCondition = (code: number): string => {
    const conditions: { [key: number]: string } = {
      0: 'Clear',
      1: 'Mainly Clear',
      2: 'Partly Cloudy',
      3: 'Overcast',
      45: 'Foggy',
      48: 'Foggy',
      51: 'Light Drizzle',
      53: 'Drizzle',
      55: 'Heavy Drizzle',
      61: 'Light Rain',
      63: 'Rain',
      65: 'Heavy Rain',
      71: 'Light Snow',
      73: 'Snow',
      75: 'Heavy Snow',
      77: 'Snow Grains',
      80: 'Light Showers',
      81: 'Showers',
      82: 'Heavy Showers',
      85: 'Light Snow Showers',
      86: 'Snow Showers',
      95: 'Thunderstorm',
      96: 'Thunderstorm with Hail',
      99: 'Thunderstorm with Hail'
    }
    return conditions[code] || 'Unknown'
  }

  const getWeatherIcon = (code: number): string => {
    if (code === 0) return '☀️'
    if (code <= 2) return '🌤️'
    if (code === 3) return '☁️'
    if (code >= 45 && code <= 48) return '🌫️'
    if (code >= 51 && code <= 55) return '🌦️'
    if (code >= 61 && code <= 65) return '🌧️'
    if (code >= 71 && code <= 77) return '❄️'
    if (code >= 80 && code <= 82) return '🌧️'
    if (code >= 85 && code <= 86) return '🌨️'
    if (code >= 95) return '⛈️'
    return '🌡️'
  }

  return (
    <DraggableWidget
      id={id}
      initialX={window.innerWidth / 2}
      initialY={180}
      gestureX={gestureX}
      gestureY={gestureY}
      gestureState={gestureState}
      gestureDefinitive={gestureDefinitive}
      onPositionUpdate={onPositionUpdate}
      checkCollision={checkCollision}
      getOtherWidgets={getOtherWidgets}
      style={{
        color: 'white',
        fontSize: '12px',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        fontWeight: '300',
        whiteSpace: 'nowrap',
        width: 'auto',
        height: '80px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}
    >
      {loading ? (
        <div>Loading...</div>
      ) : error ? (
        <div style={{ fontSize: '18px' }}>⚠️ {error}</div>
      ) : weather ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '36px' }}>{weather.icon}</span>
          <div>
            <div style={{ fontSize: '36px', fontWeight: '400' }}>
              {weather.temp}°C
            </div>
            <div style={{ fontSize: '14px', opacity: 0.8 }}>
              {weather.condition} · {weather.location}
            </div>
          </div>
        </div>
      ) : null}
    </DraggableWidget>
  )
}

export default Weather

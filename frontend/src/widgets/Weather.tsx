import { useState, useEffect } from 'react'
import DraggableWidget from '../components/Widget'

interface WeatherProps {
  gestureX?: number
  gestureY?: number
  gestureState?: 'OPEN' | 'CLOSED' | 'UNKNOWN'
  gestureDefinitive?: boolean
}

interface WeatherData {
  temp: number
  condition: string
  location: string
  icon: string
}

function Weather({ gestureX, gestureY, gestureState, gestureDefinitive }: WeatherProps) {
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
      initialX={window.innerWidth / 2}
      initialY={120}
      gestureX={gestureX}
      gestureY={gestureY}
      gestureState={gestureState}
      gestureDefinitive={gestureDefinitive}
      style={{
        color: 'white',
        fontSize: '32px',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        fontWeight: '300',
        whiteSpace: 'nowrap'
      }}
    >
      {loading ? (
        <div>Loading...</div>
      ) : error ? (
        <div style={{ fontSize: '24px' }}>⚠️ {error}</div>
      ) : weather ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ fontSize: '48px' }}>{weather.icon}</span>
          <div>
            <div style={{ fontSize: '48px', fontWeight: '400' }}>
              {weather.temp}°C
            </div>
            <div style={{ fontSize: '20px', opacity: 0.8 }}>
              {weather.condition} · {weather.location}
            </div>
          </div>
        </div>
      ) : null}
    </DraggableWidget>
  )
}

export default Weather

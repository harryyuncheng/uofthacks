import { useState, useEffect, useRef } from 'react'
import DraggableWidget from '../components/Widget'

interface VoiceOrbProps {
  id: string
  gestureX?: number
  gestureY?: number
  gestureState?: 'OPEN' | 'CLOSED' | 'UNKNOWN'
  gestureDefinitive?: boolean
  onPositionUpdate?: (id: string, position: { id: string, x: number, y: number, width: number, height: number }) => void
  checkCollision?: (id: string, x: number, y: number, width: number, height: number) => { x: number, y: number }
  getOtherWidgets?: (id: string) => Array<{ id: string, x: number, y: number, width: number, height: number }>
}

function VoiceOrb({ id, gestureX, gestureY, gestureState, gestureDefinitive, onPositionUpdate, checkCollision, getOtherWidgets }: VoiceOrbProps) {
  // Volume level 0 to 1
  const [level, setLevel] = useState(0);
  // Audio context ref
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const dataArrayRef = useRef<Uint8Array | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const requestRef = useRef<number>();

  // Use state to track if we have access to microphone
  const [isListening, setIsListening] = useState(false);

  useEffect(() => {
    // Initialize Audio Context
    const initAudio = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        analyserRef.current = audioContextRef.current.createAnalyser();
        analyserRef.current.fftSize = 64; // Small size for performance
        
        sourceRef.current = audioContextRef.current.createMediaStreamSource(stream);
        sourceRef.current.connect(analyserRef.current);
        
        const bufferLength = analyserRef.current.frequencyBinCount;
        dataArrayRef.current = new Uint8Array(bufferLength);
        
        setIsListening(true);
        animate();
      } catch (err) {
        console.error("Error accessing microphone:", err);
      }
    };

    initAudio();

    return () => {
      if (requestRef.current) cancelAnimationFrame(requestRef.current);
      if (audioContextRef.current) audioContextRef.current.close();
    };
  }, []);

  const animate = () => {
    if (!analyserRef.current || !dataArrayRef.current) return;

    analyserRef.current.getByteFrequencyData(dataArrayRef.current);
    
    // Calculate average volume
    let sum = 0;
    for (let i = 0; i < dataArrayRef.current.length; i++) {
        sum += dataArrayRef.current[i];
    }
    const average = sum / dataArrayRef.current.length;
    
    // Normalize to 0-1 (approximate max volume as 128 for speech)
    const normalizedLevel = Math.min(average / 100, 1) + 0.1; // Add base size
    
    // Apply smoothing
    setLevel(prev => prev * 0.8 + normalizedLevel * 0.2);

    requestRef.current = requestAnimationFrame(animate);
  };

  // Dynamic Styles
  const size = 100 * (0.8 + level); // Base size + pulse
  const color = `rgba(255, 255, 255, ${0.4 + level * 0.5})`; // Brighter when louder
  const glow = `0 0 ${20 + level * 40}px rgba(100, 200, 255, ${0.5 + level})`;

  return (
    <DraggableWidget
      id={id}
      initialX={window.innerWidth / 2}
      initialY={window.innerHeight / 2}
      gestureX={gestureX}
      gestureY={gestureY}
      gestureState={gestureState}
      gestureDefinitive={gestureDefinitive}
      onPositionUpdate={onPositionUpdate}
      checkCollision={checkCollision}
      getOtherWidgets={getOtherWidgets}
    >
      <div style={{
          position: 'relative',
          width: '200px',
          height: '200px',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          pointerEvents: 'none' // Let dragging handle interactions
      }}>
          {/* Main Pulsing Orb */}
          <div style={{
              width: `${size}px`,
              height: `${size}px`,
              borderRadius: '50%',
              backgroundColor: color,
              boxShadow: glow,
              transition: 'all 0.05s ease-out', // Fast transition for responsiveness
              border: '2px solid rgba(255, 255, 255, 0.8)'
          }} />
          
          {/* Inner Core */}
          <div style={{
              position: 'absolute',
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              backgroundColor: '#fff',
              boxShadow: '0 0 20px rgba(255, 255, 255, 0.9)'
          }} />
          
          {/* Label */}
          {!isListening && (
              <div style={{
                  position: 'absolute',
                  bottom: -30,
                  fontSize: '12px',
                  color: 'rgba(255,255,255,0.5)'
              }}>
                  Microphone Off
              </div>
          )}
      </div>
    </DraggableWidget>
  )
}

export default VoiceOrb
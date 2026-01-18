import { useEffect, useRef, useState, forwardRef, useImperativeHandle } from 'react'

export interface AudioBorderHandle {
  playAudio: (src: string) => void;
  audioRef: React.RefObject<HTMLAudioElement>;
}

interface AudioBorderProps {
  children: React.ReactNode;
}

const AudioBorder = forwardRef<AudioBorderHandle, AudioBorderProps>(({ children }, ref) => {
  // Audio Analysis for Border Pulse
  const [audioLevel, setAudioLevel] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const rafRef = useRef<number>();

  useImperativeHandle(ref, () => ({
    playAudio: (src: string) => {
        if (audioRef.current) {
            audioRef.current.src = src;
            audioRef.current.play().catch(e => console.error("Play error", e));
        }
    },
    audioRef: audioRef
  }));

  const initAudio = () => {
    if (!audioRef.current || audioContextRef.current) return;

    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const ctx = new AudioContextClass();
      audioContextRef.current = ctx;

      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      analyserRef.current = analyser;

      const source = ctx.createMediaElementSource(audioRef.current);
      source.connect(analyser);
      source.connect(ctx.destination); // Connect to speakers
      sourceRef.current = source;

      const animate = () => {
        if (!analyser) return;
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(dataArray);

        // Calc average val
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        const avg = sum / dataArray.length;
        // Normalize 0-1 approx
        const norm = Math.min(avg / 100, 1);
        
        setAudioLevel(prev => prev * 0.8 + norm * 0.2); // Smooth
        rafRef.current = requestAnimationFrame(animate);
      };
      animate();
    } catch (e) {
      console.error("Audio Context Init Error", e);
    }
  };

  // Resume audio context on user interaction if needed (browser policy)
  useEffect(() => {
    const handleInteract = () => {
      audioContextRef.current?.resume();
    };
    window.addEventListener('click', handleInteract);
    return () => window.removeEventListener('click', handleInteract);
  }, []);

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      backgroundColor: '#000',
      position: 'relative',
      overflow: 'hidden',
      // Dynamic Border Pulsing
      display: 'flex', // ensure children fill appropriately if needed
      boxSizing: 'border-box',
      border: `${10 + audioLevel * 20}px solid rgba(0, 255, 100, ${audioLevel * 0.8})`,
      transition: 'border 0.05s ease-out', // slightly faster transition
      boxShadow: `inset 0 0 ${50 + audioLevel * 100}px rgba(0, 255, 100, ${audioLevel * 0.5})`
    }}>
      {children}
      
      {/* Hidden Audio Element for TTS Output and Visualization */}
      <audio 
        ref={audioRef} 
        onPlay={initAudio} 
        crossOrigin="anonymous" 
        style={{ display: 'none' }} 
      />
    </div>
  );
});

export default AudioBorder;

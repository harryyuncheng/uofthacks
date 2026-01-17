import React from 'react';

interface CursorProps {
  x: number;
  y: number;
  size?: number;
  state?: 'OPEN' | 'CLOSED' | 'UNKNOWN';
}

const Cursor: React.FC<CursorProps> = ({ x, y, size = 30, state = 'UNKNOWN' }) => {
  // Change color based on state
  let backgroundColor = 'rgba(200, 200, 200, 0.5)'; // default grey
  
  if (state === 'CLOSED') {
    backgroundColor = 'rgba(0, 255, 0, 0.6)'; // green when closed (grabbing)
  } else if (state === 'OPEN') {
    backgroundColor = 'rgba(255, 0, 0, 0.5)'; // red when open
  }
  
  return (
    <div
      style={{
        position: 'fixed',
        left: x - size / 2,
        top: y - size / 2,
        width: size,
        height: size,
        borderRadius: '50%',
        backgroundColor,
        pointerEvents: 'none',
        zIndex: 9999,
        transition: 'left 0.05s ease-out, top 0.05s ease-out, width 0.1s ease, height 0.1s ease, background-color 0.2s ease',
        border: state === 'CLOSED' ? '2px solid rgba(0, 255, 0, 0.8)' : 'none',
      }}
    />
  );
};

export default Cursor;

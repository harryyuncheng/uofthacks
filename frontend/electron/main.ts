import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'path';
import { spawn, ChildProcess } from 'child_process';

const isDev = process.env.NODE_ENV === 'development';

let mainWindow: BrowserWindow | null = null;
let gestureProcess: ChildProcess | null = null;
let nfcProcess: ChildProcess | null = null;
let voiceProcess: ChildProcess | null = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Start gesture tracking automatically when window is ready
  mainWindow.webContents.on('did-finish-load', () => {
    console.log('[MAIN] Window finished loading, starting services');
    startGestureTracking();
    startNFCService();
    startVoiceTracking();
  });
}

function startVoiceTracking() {
  if (voiceProcess) {
    console.log('[MAIN] Voice tracking already running');
    return;
  }

  const voicePath = path.join(__dirname, '../../backend/Voice');
  const scriptPath = path.join(voicePath, 'llm_voice_chat.py');

  console.log('[MAIN] Starting voice tracking');
  
  voiceProcess = spawn('/Users/harry/anaconda3/bin/python', ['-u', scriptPath], {
    cwd: voicePath,
    env: { ...process.env, PYTHONUNBUFFERED: '1' } // Ensure env vars are passed
  });

  voiceProcess.stdout?.on('data', (data) => {
    const lines = data.toString().split('\n').filter((line: string) => line.trim());
    lines.forEach((line: string) => {
      try {
        // Log all output for debugging
        console.log('[VOICE RAW]', line);
        
        // Look for JSON messages
        if (line.trim().startsWith('{')) {
            const msg = JSON.parse(line);
            if (msg.type === 'voice') {
                console.log('[MAIN] Voice event detected:', msg.status);
                mainWindow?.webContents.send('voice-data', msg);
            }
        }
      } catch (err) {
        // Ignore JSON parse errors for non-JSON lines
      }
    });
  });

  voiceProcess.stderr?.on('data', (data) => {
    console.log('[VOICE ERR]', data.toString().trim());
  });

  voiceProcess.on('exit', (code) => {
    console.log(`[MAIN] Voice process exited with code ${code}`);
    voiceProcess = null;
  });
}

function startGestureTracking() {
  if (gestureProcess) {
    console.log('[MAIN] Gesture tracking already running');
    return;
  }

  // Path to the Python script
  const backendPath = path.join(__dirname, '../../backend');
  const scriptPath = path.join(backendPath, 'gesture_stream.py');

  console.log('[MAIN] Starting gesture tracking');
  console.log('[MAIN] Backend path:', backendPath);
  console.log('[MAIN] Script path:', scriptPath);
  console.log('[MAIN] __dirname:', __dirname);

  // Spawn Python process (use full path to ensure correct environment)
  // -u flag forces unbuffered output
  gestureProcess = spawn('/Users/dganjali/.pyenv/shims/python', ['-u', scriptPath], {
    cwd: backendPath,
  });

  // Handle stdout (gesture data)
  gestureProcess.stdout?.on('data', (data) => {
    const lines = data.toString().split('\n').filter((line: string) => line.trim());
    
    console.log(`[MAIN] Received ${lines.length} lines from gesture stream`);
    
    lines.forEach((line: string) => {
      try {
        const gestureData = JSON.parse(line);
        
        // Map camera coordinates to screen coordinates
        if (gestureData.hand && mainWindow) {
          const bounds = mainWindow.getBounds();
          const camWidth = gestureData.screen_size.width;
          const camHeight = gestureData.screen_size.height;
          
          // Normalize and map to window dimensions
          gestureData.hand.x = (gestureData.hand.x / camWidth) * bounds.width;
          gestureData.hand.y = (gestureData.hand.y / camHeight) * bounds.height;
        }
        
        // Send to renderer
        mainWindow?.webContents.send('gesture-data', gestureData);
      } catch (err) {
        console.error('[MAIN] Failed to parse gesture data:', err);
        console.error('[MAIN] Raw line:', line);
      }
    });
  });

  // Handle stderr (logs)
  gestureProcess.stderr?.on('data', (data) => {
    console.log('[GESTURE]', data.toString().trim());
  });

  // Handle process exit
  gestureProcess.on('exit', (code) => {
    console.log(`[MAIN] Gesture process exited with code ${code}`);
    gestureProcess = null;
  });
}

function stopGestureTracking() {
  if (gestureProcess) {
    console.log('[MAIN] Stopping gesture tracking');
    gestureProcess.kill();
    gestureProcess = null;
  }
}

function startNFCService() {
  if (nfcProcess) {
    console.log('[MAIN] NFC service already running');
    return;
  }

  const backendPath = path.join(__dirname, '../../coach_backend');
  const scriptPath = path.join(backendPath, 'arduino_listener.py');

  console.log('[MAIN] Starting NFC service...');
  
  // Reuse same python path for consistency
  nfcProcess = spawn('/Users/dganjali/.pyenv/shims/python', ['-u', scriptPath], {
    cwd: backendPath,
  });

  nfcProcess.stdout?.on('data', (data) => {
    // Unlike gestures which are high frequency, NFC events are rare.
    // We can just parse the buffer string directly.
    const output = data.toString().trim();
    // Only log if it looks meaningful or debug is needed (filter raw info logs)
    // console.log('[NFC RAW]', output); 
    
    // It might output multiple JSONs if buffered, so split by newline
    const lines = output.split('\n');
    
    lines.forEach((line: string) => {
        try {
            if (!line) return;
            // Filter out non-JSON debug lines to avoid cluttering error logs
            if (!line.trim().startsWith('{')) {
               console.log('[NFC LOG]', line.trim());
               return;
            }
            const jsonData = JSON.parse(line);
            console.log('[NFC EVENT]', jsonData);
            mainWindow?.webContents.send('nfc-event', jsonData);
        } catch (e) {
            // console.error('[NFC ERROR] Failed to parse:', line);
        }
    });
  });

  nfcProcess.stderr?.on('data', (data) => {
    console.log('[NFC DEBUG]', data.toString().trim());
  });
  
  nfcProcess.on('exit', (code) => {
      console.log(`[MAIN] NFC Process exited code: ${code}`);
      nfcProcess = null;
  });
}

function startVoiceService(prompt: string, greeting: string) {
  if (voiceProcess) {
    console.log('[MAIN] Stopping existing voice service...');
    voiceProcess.kill();
    voiceProcess = null;
  }

  const backendPath = path.join(__dirname, '../../backend');
  const scriptPath = path.join(backendPath, 'Voice/llm_voice_chat.py');

  console.log('[MAIN] Starting voice service...');
  console.log('[MAIN] Greeting:', greeting);

  voiceProcess = spawn('/Users/dganjali/.pyenv/shims/python', [
    '-u', 
    scriptPath, 
    '--prompt', prompt,
    '--greeting', greeting
  ], {
    cwd: backendPath,
    stdio: 'inherit' // Pipe output to parent console for debugging
  });

  voiceProcess.on('exit', (code) => {
      console.log(`[MAIN] Voice Process exited code: ${code}`);
      voiceProcess = null;
  });
}

// IPC handlers
ipcMain.on('start-gesture-tracking', () => {
  startGestureTracking();
});

ipcMain.on('stop-gesture-tracking', () => {
  stopGestureTracking();
});

ipcMain.on('start-voice-chat', (event, args) => {
    startVoiceService(args.prompt, args.greeting);
});

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  stopGestureTracking();
  if (voiceProcess) {
    voiceProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopGestureTracking();
  if (voiceProcess) {
    voiceProcess.kill();
  }
});

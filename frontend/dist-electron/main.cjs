"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const path_1 = __importDefault(require("path"));
const child_process_1 = require("child_process");
const isDev = process.env.NODE_ENV === 'development';
let mainWindow = null;
let gestureProcess = null;
let voiceProcess = null;
function createWindow() {
    mainWindow = new electron_1.BrowserWindow({
        width: 1000,
        height: 800,
        webPreferences: {
            preload: path_1.default.join(__dirname, 'preload.cjs'),
            nodeIntegration: false,
            contextIsolation: true,
        },
    });
    if (isDev) {
        mainWindow.loadURL('http://localhost:5173');
        mainWindow.webContents.openDevTools();
    }
    else {
        mainWindow.loadFile(path_1.default.join(__dirname, '../dist/index.html'));
    }
    mainWindow.on('closed', () => {
        mainWindow = null;
    });
    // Start gesture tracking automatically when window is ready
    mainWindow.webContents.on('did-finish-load', () => {
        console.log('[MAIN] Window finished loading, starting gesture tracking');
        startGestureTracking();
        startVoiceTracking();
    });
}
function startVoiceTracking() {
    if (voiceProcess) {
        console.log('[MAIN] Voice tracking already running');
        return;
    }
    const voicePath = path_1.default.join(__dirname, '../../backend/Voice');
    const scriptPath = path_1.default.join(voicePath, 'llm_voice_chat.py');
    console.log('[MAIN] Starting voice tracking');
    voiceProcess = (0, child_process_1.spawn)('/Users/harry/anaconda3/bin/python', ['-u', scriptPath], {
        cwd: voicePath,
        env: { ...process.env, PYTHONUNBUFFERED: '1' } // Ensure env vars are passed
    });
    voiceProcess.stdout?.on('data', (data) => {
        const lines = data.toString().split('\n').filter((line) => line.trim());
        lines.forEach((line) => {
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
            }
            catch (err) {
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
    const backendPath = path_1.default.join(__dirname, '../../backend');
    const scriptPath = path_1.default.join(backendPath, 'gesture_stream.py');
    console.log('[MAIN] Starting gesture tracking');
    console.log('[MAIN] Backend path:', backendPath);
    console.log('[MAIN] Script path:', scriptPath);
    console.log('[MAIN] __dirname:', __dirname);
    // Spawn Python process (use full path to ensure correct environment)
    // -u flag forces unbuffered output
    gestureProcess = (0, child_process_1.spawn)('/Users/harry/anaconda3/bin/python', ['-u', scriptPath], {
        cwd: backendPath,
    });
    // Handle stdout (gesture data)
    gestureProcess.stdout?.on('data', (data) => {
        const lines = data.toString().split('\n').filter((line) => line.trim());
        console.log(`[MAIN] Received ${lines.length} lines from gesture stream`);
        lines.forEach((line) => {
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
            }
            catch (err) {
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
// IPC handlers
electron_1.ipcMain.on('start-gesture-tracking', () => {
    startGestureTracking();
});
electron_1.ipcMain.on('stop-gesture-tracking', () => {
    stopGestureTracking();
});
electron_1.app.whenReady().then(() => {
    createWindow();
    electron_1.app.on('activate', () => {
        if (electron_1.BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});
electron_1.app.on('window-all-closed', () => {
    stopGestureTracking();
    if (process.platform !== 'darwin') {
        electron_1.app.quit();
    }
});
electron_1.app.on('before-quit', () => {
    stopGestureTracking();
});

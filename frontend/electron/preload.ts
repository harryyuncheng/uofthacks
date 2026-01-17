const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
  // Add any APIs you want to expose to the renderer process here
  send: (channel: string, data?: any) => {
    ipcRenderer.send(channel, data);
  },
  on: (channel: string, func: (...args: any[]) => void) => {
    const subscription = (event: any, ...args: any[]) => func(...args);
    ipcRenderer.on(channel, subscription);
    return () => {
      ipcRenderer.removeListener(channel, subscription);
    };
  },
});

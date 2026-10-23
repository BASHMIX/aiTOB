import { app, BrowserWindow, ipcMain, shell, dialog } from 'electron';
import dgram from 'dgram';
import path from 'path';
import fs from 'fs';
import { exec } from 'child_process';

let mainWindow: BrowserWindow | null = null;
let udpSocket: dgram.Socket | null = null;
let lastPacketTimestamp = 0;
let packetCount = 0;
let UDP_PORT = 8080;
let UDP_HOST = '127.0.0.1';

let fileWatcherInterval: NodeJS.Timeout | null = null;
let lastFileHash = '';
let connectionMethod: 'udp' | 'json' = 'json';
let customGamePath = '';

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1240,
    height: 820,
    minWidth: 1024,
    minHeight: 680,
    backgroundColor: '#07090e',
    title: 'aiTOB Station Agent - SF6 Telemetry & OBS Bridge',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
    },
    autoHideMenuBar: true,
  });

  const isDev = process.env.ELECTRON_IS_DEV === '1' || !app.isPackaged;

  if (isDev) {
    mainWindow.loadURL('http://localhost:5174');
    // Open DevTools in dev mode if needed
    // mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    console.error(`[Renderer Load Failed] Code: ${errorCode}, Description: ${errorDescription}, URL: ${validatedURL}`);
  });

  mainWindow.webContents.on('before-input-event', (event, input) => {
    if (input.key === 'F12' && input.type === 'keyDown') {
      mainWindow?.webContents.toggleDevTools();
      event.preventDefault();
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function startUdpListener() {
  if (udpSocket) {
    try {
      udpSocket.close();
    } catch (e) {
      // ignore
    }
    udpSocket = null;
  }

  udpSocket = dgram.createSocket('udp4');

  udpSocket.on('error', (err) => {
    console.error(`[UDP Server Error]: ${err.message}`);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('udp-status', {
        status: 'ERROR',
        message: err.message,
        port: UDP_PORT,
      });
    }
  });

  udpSocket.on('message', (msg, rinfo) => {
    try {
      const rawText = msg.toString('utf-8');
      const telemetryData = JSON.parse(rawText);
      lastPacketTimestamp = Date.now();
      packetCount += 1;

      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('game-telemetry', {
          data: telemetryData,
          rinfo: { address: rinfo.address, port: rinfo.port },
          timestamp: lastPacketTimestamp,
          packetCount,
        });
      }
    } catch (err: any) {
      console.warn(`[UDP] Failed to parse JSON packet from ${rinfo.address}:${rinfo.port}:`, err.message);
    }
  });

  udpSocket.on('listening', () => {
    const address = udpSocket?.address();
    console.log(`[UDP Server] Listening for SF6 telemetry on ${address?.address}:${address?.port}`);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('udp-status', {
        status: 'LISTENING',
        port: address?.port || UDP_PORT,
        address: address?.address || UDP_HOST,
      });
    }
  });

  try {
    udpSocket.bind(UDP_PORT, UDP_HOST);
  } catch (err: any) {
    console.error(`[UDP Server] Bind failed:`, err.message);
  }
}

function startFileWatcherFallback() {
  if (connectionMethod !== 'json') return;
  
  if (fileWatcherInterval) clearInterval(fileWatcherInterval);
  
  const attemptWatch = (sf6Path: string) => {
    const sf6Dir = path.dirname(sf6Path);
    const telemetryFile = path.join(sf6Dir, 'reframework', 'data', 'aitob_telemetry.json');
    
    console.log("[File Watcher] Found telemetry file:", telemetryFile);
    
    fileWatcherInterval = setInterval(() => {
      if (fs.existsSync(telemetryFile)) {
        try {
          const stats = fs.statSync(telemetryFile);
          const currentHash = stats.mtimeMs.toString();
          if (currentHash !== lastFileHash) {
            lastFileHash = currentHash;
            const rawText = fs.readFileSync(telemetryFile, 'utf-8');
            const telemetryData = JSON.parse(rawText);
            lastPacketTimestamp = Date.now();
            packetCount += 1;
            
            if (mainWindow && !mainWindow.isDestroyed()) {
              mainWindow.webContents.send('game-telemetry', {
                data: telemetryData,
                rinfo: { address: 'LocalFile', port: UDP_PORT },
                timestamp: lastPacketTimestamp,
                packetCount,
              });
            }
          }
        } catch (e) {
          // ignore read errors
        }
      }
    }, 500) as any;
  };

  if (customGamePath) {
    attemptWatch(customGamePath);
  } else {
    // Find SF6 path via PowerShell
    exec('powershell -Command "(Get-Process -Name \'StreetFighter6\' -ErrorAction SilentlyContinue).Path"', (err, stdout) => {
      if (err || !stdout.trim()) {
        console.log("[File Watcher] SF6 process not found, will retry later.");
        fileWatcherInterval = setTimeout(startFileWatcherFallback, 5000) as any;
        return;
      }
      attemptWatch(stdout.trim());
    });
  }
}

// IPC Handlers
ipcMain.handle('get-app-info', () => {
  return {
    version: app.getVersion(),
    platform: process.platform,
    udpPort: UDP_PORT,
    udpHost: UDP_HOST,
    packetCount,
    lastPacketTimestamp,
  };
});

ipcMain.handle('restart-udp', () => {
  startUdpListener();
  return { success: true };
});

ipcMain.handle('simulate-telemetry', (_event, simulatedData) => {
  lastPacketTimestamp = Date.now();
  packetCount += 1;
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('game-telemetry', {
      data: simulatedData,
      rinfo: { address: '127.0.0.1 (SIMULATED)', port: 8080 },
      timestamp: lastPacketTimestamp,
      packetCount,
    });
  }
  return { success: true };
});

ipcMain.handle('select-directory', async () => {
  const result = await dialog.showOpenDialog({ properties: ['openDirectory', 'openFile'] });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle('update-game-connection', (_event, config) => {
  connectionMethod = config.method;
  UDP_PORT = config.port || 8080;
  customGamePath = config.gamePath || '';
  
  // Restart listeners based on new config
  if (udpSocket) {
    try { udpSocket.close(); } catch (e) {}
    udpSocket = null;
  }
  if (fileWatcherInterval) clearInterval(fileWatcherInterval);
  
  if (connectionMethod === 'udp') {
    startUdpListener();
  } else {
    startFileWatcherFallback();
  }
  return { success: true };
});

ipcMain.handle('install-mod', async (_event, { gamePath, port }) => {
  try {
    const isExe = gamePath.toLowerCase().endsWith('.exe');
    const targetDir = isExe ? path.dirname(gamePath) : gamePath;
    
    const autorunDir = path.join(targetDir, 'reframework', 'autorun');
    if (!fs.existsSync(autorunDir)) {
      fs.mkdirSync(autorunDir, { recursive: true });
    }
    
    const isDev = process.env.ELECTRON_IS_DEV === '1' || !app.isPackaged;
    const modDir = isDev 
      ? path.join(__dirname, '../sf6_mod_files')
      : path.join(process.resourcesPath, 'sf6_mod_files');
      
    const sourceFile = path.join(modDir, 'aitob_telemetry.lua');
    let modScript = fs.readFileSync(sourceFile, 'utf-8');
    
    // Replace the port if it changed
    modScript = modScript.replace(/destination_port\s*=\s*\d+,/, `destination_port          = ${port},`);
    
    const destFile = path.join(autorunDir, 'aitob_telemetry.lua');
    fs.writeFileSync(destFile, modScript);
    
    return { success: true };
  } catch (err: any) {
    console.error("Mod install error:", err);
    return { success: false, error: err.message };
  }
});

app.whenReady().then(() => {
  createWindow();
  startUdpListener();
  startFileWatcherFallback();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (fileWatcherInterval) clearInterval(fileWatcherInterval);
  if (udpSocket) {
    try {
      udpSocket.close();
    } catch (e) {
      // ignore
    }
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

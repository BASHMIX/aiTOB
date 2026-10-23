import { spawn } from 'child_process';
import * as esbuild from 'esbuild';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function buildElectron() {
  console.log('[Runner] Bundling Electron main and preload scripts...');
  await esbuild.build({
    entryPoints: [
      path.join(__dirname, 'electron/main.ts'),
      path.join(__dirname, 'electron/preload.ts'),
    ],
    bundle: true,
    platform: 'node',
    target: 'node20',
    outdir: path.join(__dirname, 'dist-electron'),
    outExtension: { '.js': '.cjs' },
    external: ['electron'],
    sourcemap: 'inline',
  });
  console.log('[Runner] Electron scripts compiled successfully.');
}

async function start() {
  try {
    await buildElectron();

    console.log('[Runner] Starting Vite dev server...');
    const npxCmd = process.platform === 'win32' ? 'npx.cmd' : 'npx';
    const viteProcess = spawn(npxCmd, ['vite', '--port', '5174'], {
      cwd: __dirname,
      stdio: 'inherit',
      shell: true,
    });

    // Wait a brief moment for Vite to bind port 5174
    console.log('[Runner] Waiting for Vite server on http://localhost:5174...');
    await new Promise((resolve) => setTimeout(resolve, 2500));

    console.log('[Runner] Launching Electron window...');
    const electronCmd = process.platform === 'win32' ? 'npx.cmd' : 'npx';
    const electronProcess = spawn(electronCmd, ['electron', '.'], {
      cwd: __dirname,
      stdio: 'inherit',
      shell: true,
      env: {
        ...process.env,
        ELECTRON_IS_DEV: '1',
      },
    });

    electronProcess.on('close', () => {
      console.log('[Runner] Electron window closed. Shutting down Vite...');
      viteProcess.kill();
      process.exit(0);
    });

    process.on('SIGINT', () => {
      viteProcess.kill();
      electronProcess.kill();
      process.exit(0);
    });
  } catch (err) {
    console.error('[Runner] Error during startup:', err);
    process.exit(1);
  }
}

// ============================================================================
// STATION AGENT PLUGIN - CURRENTLY COMMENTED OUT / DISABLED
// ============================================================================
// start();
console.log('[Runner] Station Agent plugin is currently disabled/commented out.');

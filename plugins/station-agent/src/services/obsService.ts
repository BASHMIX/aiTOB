import OBSWebSocket from 'obs-websocket-js';
import { ObsSettings } from '../types/telemetry';

class ObsService {
  private obs: OBSWebSocket | null = null;
  private isConnected: boolean = false;
  private currentScene: string = '';

  public async connect(settings: ObsSettings): Promise<boolean> {
    if (this.isConnected) {
      await this.disconnect();
    }

    try {
      this.obs = new OBSWebSocket();
      const address = `ws://${settings.ip}:${settings.port}`;
      await this.obs.connect(address, settings.password || undefined);
      this.isConnected = true;

      // Get current scene
      const sceneData = await this.obs.call('GetCurrentProgramScene');
      this.currentScene = sceneData.currentProgramSceneName;

      // Event Listeners for stability
      this.obs.on('ConnectionClosed', () => {
        this.isConnected = false;
        console.warn('[OBS] Connection closed by server');
      });
      
      this.obs.on('ConnectionError', (err: any) => {
        this.isConnected = false;
        console.error('[OBS] Connection error', err);
      });

      this.obs.on('CurrentProgramSceneChanged', (data: any) => {
        this.currentScene = data.sceneName;
      });

      return true;
    } catch (err: any) {
      console.warn('[OBS] Connection failed:', err.message || err);
      this.isConnected = false;
      this.obs = null;
      throw err;
    }
  }

  public async disconnect(): Promise<void> {
    if (this.obs && this.isConnected) {
      try {
        await this.obs.disconnect();
      } catch (e) {
        // ignore
      }
    }
    this.isConnected = false;
    this.obs = null;
  }

  public getConnected(): boolean {
    return this.isConnected;
  }

  public getCurrentScene(): string {
    return this.currentScene;
  }

  public async switchScene(sceneName: string): Promise<boolean> {
    if (!this.isConnected || !this.obs || !sceneName) {
      return false;
    }

    try {
      if (this.currentScene === sceneName) {
        return true;
      }
      await this.obs.call('SetCurrentProgramScene', { sceneName });
      this.currentScene = sceneName;
      console.log(`[OBS] Successfully switched to scene: "${sceneName}"`);
      return true;
    } catch (err: any) {
      console.error(`[OBS] Failed to switch scene to "${sceneName}":`, err.message || err);
      return false;
    }
  }

  public async toggleSource(sceneName: string, sourceName: string, enabled: boolean): Promise<boolean> {
    if (!this.isConnected || !this.obs) return false;
    try {
      const { sceneItemId } = await this.obs.call('GetSceneItemId', { sceneName, sourceName });
      await this.obs.call('SetSceneItemEnabled', { sceneName, sceneItemId, sceneItemEnabled: enabled });
      console.log(`[OBS] Toggled source "${sourceName}" to ${enabled ? 'ON' : 'OFF'}`);
      return true;
    } catch (err: any) {
      console.error(`[OBS] Failed to toggle source "${sourceName}":`, err.message || err);
      return false;
    }
  }

  public async toggleFilter(sourceName: string, filterName: string, enabled: boolean): Promise<boolean> {
    if (!this.isConnected || !this.obs) return false;
    try {
      await this.obs.call('SetSourceFilterEnabled', { sourceName, filterName, filterEnabled: enabled });
      console.log(`[OBS] Toggled filter "${filterName}" on source "${sourceName}" to ${enabled ? 'ON' : 'OFF'}`);
      return true;
    } catch (err: any) {
      console.error(`[OBS] Failed to toggle filter "${filterName}":`, err.message || err);
      return false;
    }
  }

  public async setInputSettings(inputName: string, inputSettings: any): Promise<boolean> {
    if (!this.isConnected || !this.obs) return false;
    try {
      await this.obs.call('SetInputSettings', { inputName, inputSettings });
      console.log(`[OBS] Updated text/input settings for "${inputName}"`);
      return true;
    } catch (err: any) {
      console.error(`[OBS] Failed to set input settings for "${inputName}":`, err.message || err);
      return false;
    }
  }
  public async getSceneList(): Promise<string[]> {
    if (!this.isConnected || !this.obs) return [];
    try {
      const data = await this.obs.call('GetSceneList');
      return data.scenes.map((s: any) => s.sceneName as string);
    } catch { return []; }
  }

  public async getSceneItemList(sceneName: string): Promise<string[]> {
    if (!this.isConnected || !this.obs) return [];
    try {
      const data = await this.obs.call('GetSceneItemList', { sceneName });
      return data.sceneItems.map((i: any) => i.sourceName as string);
    } catch { return []; }
  }

  public async getSourceFilterList(sourceName: string): Promise<string[]> {
    if (!this.isConnected || !this.obs) return [];
    try {
      const data = await this.obs.call('GetSourceFilterList', { sourceName });
      return data.filters.map((f: any) => f.filterName as string);
    } catch { return []; }
  }
}

export const obsService = new ObsService();

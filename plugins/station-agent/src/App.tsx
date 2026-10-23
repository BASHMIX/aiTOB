import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  PlayerState, 
  MatchStateEnum, 
  ObsSettings, 
  AitobSettings, 
  TelemetryLogEntry 
} from './types/telemetry';
import { Navbar } from './components/Navbar';
import { PlayerCard } from './components/PlayerCard';
import { MatchCenterDeck } from './components/MatchCenterDeck';
import { ControlDeck } from './components/ControlDeck';
import { SettingsModal, SettingsTab } from './components/SettingsModal';
import { SetupGuideModal } from './components/SetupGuideModal';
import { TelemetryConsole } from './components/TelemetryConsole';
import { AitobConnectionPanel } from './components/AitobConnectionPanel';
import { RoomContext } from './components/RoomContext';
import { PlayerAutomationDeck } from './components/PlayerAutomationDeck';
import { MatchAutomationDeck } from './components/MatchAutomationDeck';
import { TriggerEditorModal } from './components/TriggerEditorModal';
import { TopMenuBar } from './components/TopMenuBar';
import { obsService } from './services/obsService';
import { aitobBridgeService } from './services/aitobBridgeService';
import { automationEngine, TriggerRule } from './services/automationEngine';

const DEFAULT_AITOB_SETTINGS: AitobSettings = {
  serverUrl: 'http://localhost:8000',
  stationId: 'station-01',
  pairingToken: '',
  connected: false,
  activeSetId: 'set-live-01',
  matchTitle: 'Winners Semis',
  bestOf: 5,
};

export const App: React.FC = () => {
  // Telemetry State
  const [matchState, setMatchState] = useState<MatchStateEnum>('IDLE');
  const [roundTimer, setRoundTimer] = useState<number>(99);
  const [roundNumber, setRoundNumber] = useState<number>(1);
  const [roomId, setRoomId] = useState<string>('');
  const [gamePacketCount, setGamePacketCount] = useState<number>(0);
  const [isGameConnected, setIsGameConnected] = useState<boolean>(false);
  const lastPacketTimeRef = useRef<number>(0);
  const lastScreenRef = useRef<string>('MAIN_MENU_OR_IDLE');
  const hasIncrementedMatchRef = useRef<boolean>(false);
  const lastSyncedCharsRef = useRef<{ p1: string; p2: string; setId: string }>({ p1: '', p2: '', setId: '' });
  const lastSyncTimeRef = useRef<number>(0);
  const p1ScoreRef = useRef<number>(0);
  const p2ScoreRef = useRef<number>(0);
  const autoConfirmRef = useRef<boolean>(true);
  const aitobSettingsRef = useRef<AitobSettings>(DEFAULT_AITOB_SETTINGS);

  // Player 1 & 2
  const [p1, setP1] = useState<PlayerState>({
    characterId: 11,
    characterName: 'Ryu',
    currentHp: 10000,
    maxHp: 10000,
    roundsWon: 0,
    scoreInSet: 0,
    superArt: 2,
    driveGauge: 6.0,
    displayName: 'Player 1 (P1)',
  });

  const [p2, setP2] = useState<PlayerState>({
    characterId: 15,
    characterName: 'Ken',
    currentHp: 10000,
    maxHp: 10000,
    roundsWon: 0,
    scoreInSet: 0,
    superArt: 1,
    driveGauge: 5.5,
    displayName: 'Player 2 (P2)',
  });

  // OBS Settings & State
  const [obsSettings, setObsSettings] = useState<ObsSettings>(() => {
    const saved = localStorage.getItem('aitob_obs_settings');
    if (saved) { try { return JSON.parse(saved); } catch(e) {} }
    return {
      enabled: true,
      ip: '127.0.0.1',
      port: 4455,
      password: '',
      scenePreMatch: 'SF6 - Versus',
      sceneGameplay: 'SF6 - InGame',
      sceneVictory: 'SF6 - Victory',
      autoSwitch: true,
    };
  });
  useEffect(() => { localStorage.setItem('aitob_obs_settings', JSON.stringify(obsSettings)); }, [obsSettings]);
  const [isObsConnected, setIsObsConnected] = useState<boolean>(false);
  const [isObsConnecting, setIsObsConnecting] = useState<boolean>(false);
  
  // Unified Settings Modal
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState<boolean>(false);
  const [settingsModalTab, setSettingsModalTab] = useState<SettingsTab>('GAME');
  const [isHelpModalOpen, setIsHelpModalOpen] = useState<boolean>(false);

  // View Preferences (Logs visibility & Compact Mode)
  const [showLogs, setShowLogs] = useState<boolean>(() => {
    const saved = localStorage.getItem('aitob_show_logs');
    return saved !== null ? JSON.parse(saved) : true;
  });
  useEffect(() => { localStorage.setItem('aitob_show_logs', JSON.stringify(showLogs)); }, [showLogs]);

  const [compactMode, setCompactMode] = useState<boolean>(() => {
    const saved = localStorage.getItem('aitob_compact_mode');
    return saved !== null ? JSON.parse(saved) : false;
  });
  useEffect(() => { localStorage.setItem('aitob_compact_mode', JSON.stringify(compactMode)); }, [compactMode]);

  const [gameConnectionConfig, setGameConnectionConfig] = useState<{
    method: 'json' | 'udp';
    port: number;
    gamePath: string;
  }>(() => {
    const saved = localStorage.getItem('aitob_game_conn');
    if (saved) { try { return JSON.parse(saved); } catch(e) {} }
    return {
      method: 'json',
      port: 8080,
      gamePath: '',
    };
  });
  useEffect(() => { localStorage.setItem('aitob_game_conn', JSON.stringify(gameConnectionConfig)); }, [gameConnectionConfig]);

  // aiTOB Platform Settings & State
  const [aitobSettings, setAitobSettings] = useState<AitobSettings>(() => {
    const saved = localStorage.getItem('aitob_platform_settings');
    if (saved) { try { return JSON.parse(saved); } catch(e) {} }
    return DEFAULT_AITOB_SETTINGS;
  });
  aitobSettingsRef.current = aitobSettings;
  useEffect(() => { localStorage.setItem('aitob_platform_settings', JSON.stringify(aitobSettings)); }, [aitobSettings]);

  // Automation Toggles
  const [autoConfirm, setAutoConfirm] = useState<boolean>(true);
  const [autoObsSwitch, setAutoObsSwitch] = useState<boolean>(true);

  useEffect(() => { p1ScoreRef.current = p1.scoreInSet; }, [p1.scoreInSet]);
  useEffect(() => { p2ScoreRef.current = p2.scoreInSet; }, [p2.scoreInSet]);
  useEffect(() => { autoConfirmRef.current = autoConfirm; }, [autoConfirm]);
  useEffect(() => { aitobSettingsRef.current = aitobSettings; }, [aitobSettings]);

  // Automation Rules
  const [rules, setRules] = useState<TriggerRule[]>(() => {
    const saved = localStorage.getItem('aitob_rules');
    if (saved) { try { return JSON.parse(saved); } catch(e) {} }
    return [
      {
        id: 'rule_1', name: 'Burnout Alert', enabled: true, scope: 'P1',
        variable: 'P1_DRIVE', operator: '<=', threshold: 0.1,
        actionType: 'TOGGLE_FILTER', sourceName: 'P1_Cam', filterName: 'BurnoutShake',
        durationMode: 'WHILE_TRUE'
      },
      {
        id: 'rule_2', name: 'Low Timer Danger', enabled: true, scope: 'MATCH',
        variable: 'ROUND_TIMER', operator: '<=', threshold: 10,
        actionType: 'TOGGLE_FILTER', sourceName: 'Gameplay', filterName: 'RedFlash',
        durationMode: 'WHILE_TRUE'
      },
      {
        id: 'rule_3', name: 'Combo Breaker', enabled: true, scope: 'P2',
        variable: 'P2_COMBO', operator: '>=', threshold: 15,
        actionType: 'TOGGLE_SOURCE', sourceName: 'ComboFire',
        durationMode: 'FIXED_TIME', durationSeconds: 4
      }
    ];
  });
  useEffect(() => { localStorage.setItem('aitob_rules', JSON.stringify(rules)); }, [rules]);

  const [isTriggerModalOpen, setIsTriggerModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<TriggerRule | undefined>(undefined);
  const [triggerScope, setTriggerScope] = useState<'MATCH' | 'P1' | 'P2'>('MATCH');

  const toggleRule = (id: string) => {
    setRules(prev => prev.map(r => r.id === id ? { ...r, enabled: !r.enabled } : r));
  };

  const handleAddRule = (scope: 'MATCH' | 'P1' | 'P2') => {
    setTriggerScope(scope);
    setEditingRule(undefined);
    setIsTriggerModalOpen(true);
  };

  const handleMirrorRule = (id: string) => {
    const sourceRule = rules.find(r => r.id === id);
    if (!sourceRule || sourceRule.scope === 'MATCH') return;

    const targetScope = sourceRule.scope === 'P1' ? 'P2' : 'P1';
    
    const replaceStr = (str: string | undefined, from: string, to: string) => {
      if (!str) return str;
      return str.split(from).join(to);
    };

    const fromPattern = sourceRule.scope;
    const toPattern = targetScope;

    const newRule: TriggerRule = {
      ...sourceRule,
      id: 'rule_' + Math.random().toString(36).substr(2, 9),
      scope: targetScope,
      name: sourceRule.name.includes(fromPattern) 
        ? (replaceStr(sourceRule.name, fromPattern, toPattern) || '')
        : `${sourceRule.name} (${targetScope})`,
      variable: replaceStr(sourceRule.variable, fromPattern, toPattern) as any,
      textContent: replaceStr(sourceRule.textContent, fromPattern, toPattern)
    };

    setRules(prev => [...prev, newRule]);
    addLog('SYSTEM', `Mirrored rule: ${sourceRule.name} ➔ ${targetScope}`);
  };

  const handleEditRule = (id: string) => {
    const rule = rules.find(r => r.id === id);
    if (rule) {
      setEditingRule(rule);
      setTriggerScope(rule.scope);
      setIsTriggerModalOpen(true);
    }
  };

  const handleDeleteRule = (id: string) => {
    setRules(prev => prev.filter(r => r.id !== id));
    addLog('SYSTEM', `Deleted rule with ID: ${id}`);
    setIsTriggerModalOpen(false);
  };

  const handleSaveRule = (rule: TriggerRule) => {
    setRules(prev => {
      const exists = prev.find(r => r.id === rule.id);
      if (exists) {
        return prev.map(r => r.id === rule.id ? rule : r);
      }
      return [...prev, rule];
    });
  };

  const handleMoveRule = (id: string, direction: 'UP' | 'DOWN') => {
    setRules(prev => {
      const index = prev.findIndex(r => r.id === id);
      if (index === -1) return prev;
      const targetScope = prev[index].scope;
      const scopeIndices = prev
        .map((r, i) => (r.scope === targetScope ? i : -1))
        .filter(i => i !== -1);
      const currentScopePos = scopeIndices.indexOf(index);
      const targetScopePos = direction === 'UP' ? currentScopePos - 1 : currentScopePos + 1;
      if (targetScopePos < 0 || targetScopePos >= scopeIndices.length) return prev;
      const targetIndex = scopeIndices[targetScopePos];
      const newRules = [...prev];
      const temp = newRules[index];
      newRules[index] = newRules[targetIndex];
      newRules[targetIndex] = temp;
      return newRules;
    });
  };

  const handleReorderRules = (sourceId: string, targetId: string) => {
    setRules(prev => {
      const dragIdx = prev.findIndex(r => r.id === sourceId);
      const targetIdx = prev.findIndex(r => r.id === targetId);
      if (dragIdx === -1 || targetIdx === -1 || dragIdx === targetIdx) return prev;
      const newRules = [...prev];
      const [moved] = newRules.splice(dragIdx, 1);
      newRules.splice(targetIdx, 0, moved);
      return newRules;
    });
  };

  // Logs & Submissions
  const [logs, setLogs] = useState<TelemetryLogEntry[]>([]);
  const [lastRawPacket, setLastRawPacket] = useState<any>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitMessage, setSubmitMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const addLog = useCallback((type: 'PACKET' | 'OBS' | 'AITOB' | 'SYSTEM', message: string, raw?: any) => {
    const newEntry: TelemetryLogEntry = {
      id: Math.random().toString(36).substring(7),
      timestamp: new Date().toLocaleTimeString('ar-EG', { hour12: false }),
      type,
      message,
      raw,
    };
    setLogs((prev) => [...prev.slice(-99), newEntry]);
  }, []);

  // Heartbeat watchdog for Game UDP
  useEffect(() => {
    const interval = setInterval(() => {
      if (lastPacketTimeRef.current > 0 && Date.now() - lastPacketTimeRef.current > 4000) {
        setIsGameConnected(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // Connect to OBS on mount if enabled
  useEffect(() => {
    if (obsSettings.enabled) {
      obsService.connect(obsSettings)
        .then(() => {
          setIsObsConnected(true);
          addLog('OBS', `Connected to OBS Studio on port ${obsSettings.port}`);
        })
        .catch(() => {
          setIsObsConnected(false);
        });
    }
    return () => {
      obsService.disconnect();
    };
  }, []);

  const connectAitob = (targetSettings?: AitobSettings) => {
    const s = targetSettings || aitobSettings;
    aitobBridgeService.connect(
      s,
      (matchUpdate) => {
        setP1((prev) => ({
          ...prev,
          displayName: matchUpdate.p1.displayName || prev.displayName,
          scoreInSet: matchUpdate.p1.score ?? prev.scoreInSet,
          sponsorPrefix: matchUpdate.p1.sponsorPrefix || prev.sponsorPrefix,
          characterName: matchUpdate.p1.characterName || prev.characterName,
          characterId: matchUpdate.p1.characterId ?? prev.characterId,
        }));
        setP2((prev) => ({
          ...prev,
          displayName: matchUpdate.p2.displayName || prev.displayName,
          scoreInSet: matchUpdate.p2.score ?? prev.scoreInSet,
          sponsorPrefix: matchUpdate.p2.sponsorPrefix || prev.sponsorPrefix,
          characterName: matchUpdate.p2.characterName || prev.characterName,
          characterId: matchUpdate.p2.characterId ?? prev.characterId,
        }));
        setAitobSettings((prev) => ({
          ...prev,
          connected: true,
          activeSetId: matchUpdate.setId,
          matchTitle: matchUpdate.matchTitle,
          bestOf: matchUpdate.bestOf || prev.bestOf,
        }));
        addLog('AITOB', `Match updated: ${matchUpdate.p1.displayName} (${matchUpdate.p1.characterName || 'No Char'}) vs ${matchUpdate.p2.displayName} (${matchUpdate.p2.characterName || 'No Char'})`);
      },
      (connected) => {
        setAitobSettings((prev) => ({ ...prev, connected }));
        if (connected) {
          addLog('AITOB', `Connected to aiTOB Platform Station (${s.stationId})`);
        }
      }
    );
  };

  const disconnectAitob = () => {
    aitobBridgeService.disconnect();
    setAitobSettings((prev) => ({ ...prev, connected: false }));
    addLog('AITOB', 'Disconnected from aiTOB Platform');
  };

  // Connect to aiTOB Platform on mount or settings change
  useEffect(() => {
    connectAitob(aitobSettings);

    return () => {
      aitobBridgeService.disconnect();
    };
  }, [aitobSettings.serverUrl, aitobSettings.stationId, aitobSettings.pairingToken]);

  // Initial Game Connection Sync
  useEffect(() => {
    if (typeof window !== 'undefined' && window.api?.updateGameConnection) {
      window.api.updateGameConnection(gameConnectionConfig);
    }
  }, []);

  // Handle incoming Telemetry from Electron UDP listener
  useEffect(() => {
    if (typeof window !== 'undefined' && window.api?.onGameTelemetry) {
      const unsubscribe = window.api.onGameTelemetry((payload) => {
        lastPacketTimeRef.current = Date.now();
        setIsGameConnected(true);
        setGamePacketCount(payload.packetCount);
        setLastRawPacket(payload.data);

        const data = payload.data;
        if (!data) return;

        // Auto-Increment Set Score Logic
        if (data.p1?.rounds_won === 0 && data.p2?.rounds_won === 0 && data.screen === 'FIGHTING') {
          hasIncrementedMatchRef.current = false;
        }

        if (data.screen) {
          if (data.screen === 'MATCH_RESULTS' && !hasIncrementedMatchRef.current) {
            const p1Rounds = data.p1?.rounds_won ?? 0;
            const p2Rounds = data.p2?.rounds_won ?? 0;
            
            // Only increment if a player has actually won the game (reached 2 rounds)
            let updatedP1Score = p1ScoreRef.current;
            let updatedP2Score = p2ScoreRef.current;
            let scored = false;
            if (p1Rounds >= 2 && p1Rounds > p2Rounds) {
              updatedP1Score = p1ScoreRef.current + 1;
              p1ScoreRef.current = updatedP1Score;
              setP1(p => ({ ...p, scoreInSet: updatedP1Score }));
              scored = true;
              addLog('AITOB', `Auto-Increment: P1 won the match! Score updated.`);
              hasIncrementedMatchRef.current = true;
            } else if (p2Rounds >= 2 && p2Rounds > p1Rounds) {
              updatedP2Score = p2ScoreRef.current + 1;
              p2ScoreRef.current = updatedP2Score;
              setP2(p => ({ ...p, scoreInSet: updatedP2Score }));
              scored = true;
              addLog('AITOB', `Auto-Increment: P2 won the match! Score updated.`);
              hasIncrementedMatchRef.current = true;
            }

            if (scored && aitobSettingsRef.current.connected) {
              const activeSet = aitobSettingsRef.current.activeSetId || '';
              // 1. Sync live intermediate score to aiTOB overlay & platform
              aitobBridgeService.syncScore(updatedP1Score, updatedP2Score, activeSet);

              // 2. Check if set is concluded (reached FT target)
              const bestOf = aitobSettingsRef.current.bestOf || 5;
              const targetWins = Math.ceil(bestOf / 2);
              if (autoConfirmRef.current && (updatedP1Score >= targetWins || updatedP2Score >= targetWins)) {
                const winner = updatedP1Score >= targetWins ? 'p1' : 'p2';
                addLog('AITOB', `Auto-Reporting set completion (${updatedP1Score} - ${updatedP2Score}) for winner ${winner.toUpperCase()}...`);
                aitobBridgeService.submitMatchResult(activeSet, updatedP1Score, updatedP2Score, winner, autoConfirmRef.current)
                  .then(res => {
                    if (res.success) {
                      setSubmitMessage({ type: 'success', text: res.message });
                      addLog('AITOB', res.message);
                    } else {
                      setSubmitMessage({ type: 'error', text: res.message });
                      addLog('AITOB', res.message);
                    }
                  });
              }
            }
          }
          lastScreenRef.current = data.screen;
        }

        // Update Round & Match state
        if (data.room_id !== undefined) setRoomId(data.room_id);
        if (data.round_timer !== undefined) setRoundTimer(data.round_timer);
        if (data.round_number !== undefined) setRoundNumber(data.round_number);
        
        if (data.match_state) {
          const nextState = data.match_state as MatchStateEnum;
          setMatchState(nextState);

          // Handle automatic OBS scene switching
          if (autoObsSwitch && obsService.getConnected()) {
            if (nextState === 'FIGHTING' && obsSettings.sceneGameplay) {
              obsService.switchScene(obsSettings.sceneGameplay);
              addLog('OBS', `Auto-switched to gameplay scene: ${obsSettings.sceneGameplay}`);
            } else if (nextState === 'CHARACTER_SELECT' && obsSettings.scenePreMatch) {
              obsService.switchScene(obsSettings.scenePreMatch);
              addLog('OBS', `Auto-switched to pre-match scene: ${obsSettings.scenePreMatch}`);
            } else if (nextState === 'MATCH_OVER' && obsSettings.sceneVictory) {
              obsService.switchScene(obsSettings.sceneVictory);
              addLog('OBS', `Auto-switched to victory scene: ${obsSettings.sceneVictory}`);
            }
          }
        }

        // Update Player 1
        if (data.p1) {
          setP1((prev) => {
            const nextDrive = data.p1?.drive_gauge ?? prev.driveGauge;
            let nextIsBurnout = prev.isBurnout;
            if (nextDrive <= 0) nextIsBurnout = true;
            else if (nextDrive >= 6) nextIsBurnout = false;
            
            return {
              ...prev,
              characterId: data.p1?.character_id ?? prev.characterId,
              characterName: data.p1?.character_name || prev.characterName,
              currentHp: data.p1?.current_hp ?? prev.currentHp,
              maxHp: data.p1?.max_hp ?? prev.maxHp,
              roundsWon: data.p1?.rounds_won ?? prev.roundsWon,
              gameWins: data.p1?.game_wins ?? prev.gameWins,
              maxCombo: data.p1?.max_combo ?? prev.maxCombo,
              maxDamage: data.p1?.max_damage ?? prev.maxDamage,
              superArt: data.p1?.super_art ?? prev.superArt,
              driveGauge: nextDrive,
              isBurnout: nextIsBurnout,
            };
          });
        }

        // Update Player 2
        if (data.p2) {
          setP2((prev) => {
            const nextDrive = data.p2?.drive_gauge ?? prev.driveGauge;
            let nextIsBurnout = prev.isBurnout;
            if (nextDrive <= 0) nextIsBurnout = true;
            else if (nextDrive >= 6) nextIsBurnout = false;
            
            return {
              ...prev,
              characterId: data.p2?.character_id ?? prev.characterId,
              characterName: data.p2?.character_name || prev.characterName,
              currentHp: data.p2?.current_hp ?? prev.currentHp,
              maxHp: data.p2?.max_hp ?? prev.maxHp,
              roundsWon: data.p2?.rounds_won ?? prev.roundsWon,
              gameWins: data.p2?.game_wins ?? prev.gameWins,
              maxCombo: data.p2?.max_combo ?? prev.maxCombo,
              maxDamage: data.p2?.max_damage ?? prev.maxDamage,
              superArt: data.p2?.super_art ?? prev.superArt,
              driveGauge: nextDrive,
              isBurnout: nextIsBurnout,
            };
          });
        }

        if (data.roomId !== undefined) {
          setRoomId(data.roomId);
        }

        // Live In-Game Character Sync to aiTOB Platform
        const inP1Char = (data.p1?.character_name || '').trim();
        const inP2Char = (data.p2?.character_name || '').trim();
        const inP1Cid = data.p1?.character_id;
        const inP2Cid = data.p2?.character_id;
        const activeSet = aitobSettings.activeSetId || '';

        const isValidChar = (c: string) => Boolean(c && !['none', 'unknown', '—', '-', ''].includes(c.toLowerCase()));
        const p1Ok = isValidChar(inP1Char);
        const p2Ok = isValidChar(inP2Char);

        if (aitobSettings.connected && (p1Ok || p2Ok)) {
          const changed = inP1Char !== lastSyncedCharsRef.current.p1 || inP2Char !== lastSyncedCharsRef.current.p2 || activeSet !== lastSyncedCharsRef.current.setId;
          const now = Date.now();
          if (changed && now - lastSyncTimeRef.current > 1500) {
            lastSyncTimeRef.current = now;
            lastSyncedCharsRef.current = { p1: inP1Char, p2: inP2Char, setId: activeSet };
            aitobBridgeService.syncCharacters(
              p1Ok ? inP1Char : undefined,
              p2Ok ? inP2Char : undefined,
              inP1Cid,
              inP2Cid,
              activeSet
            ).then(() => {
              addLog('AITOB', `Reflected live in-game characters to aiTOB: P1=${inP1Char || '—'}, P2=${inP2Char || '—'}`);
            }).catch(() => {});
          }
        }
      });

      return () => {
        unsubscribe();
      };
    }
  }, [autoObsSwitch, obsSettings, addLog, aitobSettings.connected, aitobSettings.activeSetId]);

  // Evaluate Automation Rules when State Changes
  useEffect(() => {
    const telemetryData = {
      game: 'SF6',
      roundTimer,
      roundNumber,
      matchState,
      roomId,
      p1,
      p2,
      lastUpdated: Date.now()
    };
    automationEngine.evaluate(rules, telemetryData as any);
  }, [p1, p2, roundTimer, matchState, roomId, rules]);

  // Submit Result to aiTOB Platform
  const handleSubmitResult = async () => {
    setIsSubmitting(true);
    setSubmitMessage(null);

    const winner = p1.scoreInSet > p2.scoreInSet ? 'p1' : 'p2';
    const setId = aitobSettings.activeSetId || 'manual-set';

    addLog('AITOB', `Submitting set result (${p1.scoreInSet} - ${p2.scoreInSet}) to server...`);

    const res = await aitobBridgeService.submitMatchResult(
      setId,
      p1.scoreInSet,
      p2.scoreInSet,
      winner,
      autoConfirm
    );

    setIsSubmitting(false);
    if (res.success) {
      setSubmitMessage({ type: 'success', text: res.message });
      addLog('AITOB', res.message);
    } else {
      setSubmitMessage({ type: 'error', text: res.message });
      addLog('AITOB', res.message);
    }

    setTimeout(() => {
      setSubmitMessage(null);
    }, 6000);
  };

  // Reset Set
  const handleResetSet = () => {
    setP1((prev) => ({ 
      ...prev, 
      currentHp: 10000, roundsWon: 0, scoreInSet: 0,
      characterName: '', driveGauge: 6000, isBurnout: false,
      superArt: 0, maxCombo: 0, maxDamage: 0
    }));
    setP2((prev) => ({ 
      ...prev, 
      currentHp: 10000, roundsWon: 0, scoreInSet: 0,
      characterName: '', driveGauge: 6000, isBurnout: false,
      superArt: 0, maxCombo: 0, maxDamage: 0
    }));
    setRoundNumber(1);
    setRoundTimer(99);
    setMatchState('IDLE');
    addLog('SYSTEM', 'Reset set state, characters, and bars.');
  };

  // Send In-Game Invite Action
  const handleSendGameInvite = () => {
    addLog('SYSTEM', `In-game invite sent to: ${p1.displayName} and ${p2.displayName}`);
    alert(`🎮 Custom Room Invite Sent to:\n- ${p1.displayName}\n- ${p2.displayName}`);
  };

  // Simulation handlers for testing without actual game
  const handleSimulateFight = () => {
    const p1Dmg = Math.floor(Math.random() * 2500) + 1000;
    const p2Dmg = Math.floor(Math.random() * 3200) + 1200;

    const simData = {
      game: 'SF6',
      match_state: 'FIGHTING',
      round_timer: Math.max(12, roundTimer - 8),
      round_number: roundNumber,
      p1: {
        character_id: 11,
        character_name: 'Ryu',
        current_hp: Math.max(1200, p1.currentHp - p1Dmg),
        max_hp: 10000,
        rounds_won: p1.roundsWon,
        super_art: Math.min(3, p1.superArt + 1),
        drive_gauge: Math.max(1, p1.driveGauge - 1.2),
      },
      p2: {
        character_id: 15,
        character_name: 'Ken',
        current_hp: Math.max(800, p2.currentHp - p2Dmg),
        max_hp: 10000,
        rounds_won: p2.roundsWon,
        super_art: Math.min(3, p2.superArt + 1),
        drive_gauge: Math.max(0.5, p2.driveGauge - 1.5),
      },
    };

    if (window.api?.simulateTelemetry) {
      window.api.simulateTelemetry(simData);
    } else {
      // Direct state update for browser preview
      setP1((prev) => ({ ...prev, ...simData.p1 }));
      setP2((prev) => ({ ...prev, ...simData.p2 }));
      setRoundTimer(simData.round_timer);
      setMatchState('FIGHTING');
      setIsGameConnected(true);
      setGamePacketCount((c) => c + 1);
    }

    addLog('PACKET', `Simulated Hits: P1 HP: ${simData.p1.current_hp} | P2 HP: ${simData.p2.current_hp}`);
  };

  const handleSimulateFinish = () => {
    const simData = {
      game: 'SF6',
      match_state: 'MATCH_OVER',
      round_timer: 0,
      round_number: roundNumber,
      p1: {
        character_id: 11,
        character_name: 'Ryu',
        current_hp: 4200,
        max_hp: 10000,
        rounds_won: 2,
        super_art: 3,
        drive_gauge: 4.5,
      },
      p2: {
        character_id: 15,
        character_name: 'Ken',
        current_hp: 0,
        max_hp: 10000,
        rounds_won: 0,
        super_art: 1,
        drive_gauge: 0,
      },
    };

    if (window.api?.simulateTelemetry) {
      window.api.simulateTelemetry(simData);
    } else {
      setP1((prev) => ({ ...prev, ...simData.p1, scoreInSet: prev.scoreInSet + 1 }));
      setP2((prev) => ({ ...prev, ...simData.p2 }));
      setRoundTimer(0);
      setMatchState('MATCH_OVER');
      setIsGameConnected(true);
      setGamePacketCount((c) => c + 1);
    }

    addLog('PACKET', 'Simulated Final K.O. - Player 1 wins round and set.');

    if (autoConfirm) {
      setTimeout(() => {
        handleSubmitResult();
      }, 1500);
    }
  };

  return (
    <div className="min-h-screen bg-[#07090e] text-slate-100 flex flex-col justify-between selection:bg-cyan-500 selection:text-black">
      {/* Top Menu Bar (File, Edit, View, Help) */}
      <TopMenuBar 
        onOpenSettings={(tab) => {
          setSettingsModalTab(tab || 'GAME');
          setIsSettingsModalOpen(true);
        }}
        rules={rules} setRules={setRules}
        obsSettings={obsSettings} setObsSettings={setObsSettings}
        aitobSettings={aitobSettings} setAitobSettings={setAitobSettings}
        gameConnectionConfig={gameConnectionConfig} setGameConnectionConfig={setGameConnectionConfig}
        onClearLogs={() => setLogs([])}
        onResetMatch={handleResetSet}
        showLogs={showLogs}
        onToggleLogs={() => setShowLogs(prev => !prev)}
        compactMode={compactMode}
        onToggleCompactMode={() => setCompactMode(prev => !prev)}
        onOpenHelp={() => setIsHelpModalOpen(true)}
      />
      
      {/* Top Navbar */}
      <Navbar
        stationId={aitobSettings.stationId}
        isGameConnected={isGameConnected}
        gamePacketCount={gamePacketCount}
        gamePort={gameConnectionConfig.port}
        gameMethod={gameConnectionConfig.method}
        isObsConnected={isObsConnected}
        obsPort={obsSettings.port}
        isAitobConnected={aitobSettings.connected}
        onOpenGameSettings={() => {
          setSettingsModalTab('GAME');
          setIsSettingsModalOpen(true);
        }}
        onOpenObsSettings={() => {
          setSettingsModalTab('OBS');
          setIsSettingsModalOpen(true);
        }}
        onOpenAitobSettings={() => {
          setSettingsModalTab('AITOB');
          setIsSettingsModalOpen(true);
        }}
        onSimulateFight={handleSimulateFight}
        onSimulateFinish={handleSimulateFinish}
        compactMode={compactMode}
      />

      <main className={`flex-1 max-w-7xl w-full mx-auto ${compactMode ? 'px-4 py-2' : 'px-6 py-6'} flex flex-col`}>
        {/* 1. aiTOB Station Connection Panel (Hidden in Compact Mode) */}
        {!compactMode && (
          <AitobConnectionPanel 
            settings={aitobSettings}
            onSettingsChange={(newSettings) => {
              setAitobSettings(newSettings);
            }}
            onConnect={() => connectAitob(aitobSettings)}
            onDisconnect={disconnectAitob}
            onSync={() => connectAitob(aitobSettings)}
          />
        )}

        {/* 2. Room Context Details (Hidden in Compact Mode) */}
        {!compactMode && (
          <RoomContext 
            roomId={roomId}
            matchState={matchState}
            p1GameWins={p1.gameWins || 0}
            p2GameWins={p2.gameWins || 0}
          />
        )}

        {/* 3. Main VS Arena Display */}
        <div className={`grid grid-cols-1 lg:grid-cols-12 gap-6 items-start ${compactMode ? 'mt-1' : 'mt-2'}`}>
          {/* Player 1 Col (Cols 5) */}
          <div className="lg:col-span-5 flex flex-col">
            <PlayerCard
              playerNumber={1}
              player={p1}
              onScoreChange={(score) => setP1((prev) => ({ ...prev, scoreInSet: score }))}
              onNameChange={(name) => setP1((prev) => ({ ...prev, displayName: name }))}
              bestOf={aitobSettings.bestOf}
            />
            {!compactMode && (
              <PlayerAutomationDeck 
                playerNumber={1} 
                rules={rules} 
                onToggleRule={toggleRule} 
                onAddRule={handleAddRule}
                onEditRule={handleEditRule}
                onMirrorRule={handleMirrorRule}
                onMoveRule={handleMoveRule}
                onReorderRules={handleReorderRules}
              />
            )}
          </div>

          {/* Match Center Col (Cols 2) */}
          <div className="lg:col-span-2 flex flex-col">
            <MatchCenterDeck
              matchState={matchState}
              roundTimer={roundTimer}
              roundNumber={roundNumber}
              matchTitle={aitobSettings.matchTitle}
              bestOf={aitobSettings.bestOf}
              onResetSet={handleResetSet}
              onChangeBestOf={(num) => setAitobSettings(prev => ({ ...prev, bestOf: num }))}
            />
            {!compactMode && (
              <MatchAutomationDeck 
                rules={rules} 
                onToggleRule={toggleRule} 
                onAddRule={handleAddRule}
                onEditRule={handleEditRule}
                onMoveRule={handleMoveRule}
                onReorderRules={handleReorderRules}
              />
            )}
          </div>

          {/* Player 2 Col (Cols 5) */}
          <div className="lg:col-span-5 flex flex-col">
            <PlayerCard
              playerNumber={2}
              player={p2}
              onScoreChange={(score) => setP2((prev) => ({ ...prev, scoreInSet: score }))}
              onNameChange={(name) => setP2((prev) => ({ ...prev, displayName: name }))}
              bestOf={aitobSettings.bestOf}
            />
            {!compactMode && (
              <PlayerAutomationDeck 
                playerNumber={2} 
                rules={rules} 
                onToggleRule={toggleRule} 
                onAddRule={handleAddRule}
                onEditRule={handleEditRule}
                onMirrorRule={handleMirrorRule}
                onMoveRule={handleMoveRule}
                onReorderRules={handleReorderRules}
              />
            )}
          </div>
        </div>
      </main>

      {/* Live Telemetry Console (Collapsible & Toggled from View menu, hidden in compact mode) */}
      {showLogs && !compactMode && (
        <TelemetryConsole
          logs={logs}
          onClear={() => setLogs([])}
          lastRawPacket={lastRawPacket}
        />
      )}

      {/* Bottom Control Deck */}
      <ControlDeck
        onSendGameInvite={handleSendGameInvite}
        onSubmitResult={handleSubmitResult}
        onResetSet={handleResetSet}
        autoConfirm={autoConfirm}
        onToggleAutoConfirm={() => setAutoConfirm(!autoConfirm)}
        autoObsSwitch={autoObsSwitch}
        onToggleAutoObsSwitch={() => setAutoObsSwitch(!autoObsSwitch)}
        isSubmitting={isSubmitting}
        submitMessage={submitMessage}
      />

      {/* Unified Settings Modal */}
      <SettingsModal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        defaultTab={settingsModalTab}
        gameConnectionConfig={gameConnectionConfig}
        onSaveGameConfig={async (config) => {
          setGameConnectionConfig(config);
          if (typeof window !== 'undefined' && window.api?.updateGameConnection) {
            await window.api.updateGameConnection(config);
          }
        }}
        obsSettings={obsSettings}
        onSaveObsSettings={(newSettings) => {
          setObsSettings(newSettings);
          obsService.connect(newSettings).then(() => setIsObsConnected(true)).catch(() => setIsObsConnected(false));
        }}
        isObsConnected={isObsConnected}
        isObsConnecting={isObsConnecting}
        onTestObsConnection={async () => {
          setIsObsConnecting(true);
          try {
            if (isObsConnected) {
              await obsService.disconnect();
              setIsObsConnected(false);
              addLog('OBS', 'Disconnected from OBS Studio');
            } else {
              await obsService.connect(obsSettings);
              setIsObsConnected(true);
              addLog('OBS', `Successfully connected to OBS Studio (${obsSettings.ip}:${obsSettings.port})`);
            }
          } catch (err: any) {
            alert(`Failed to connect to OBS Studio:\n${err.message || err}\nMake sure WebSocket Server is enabled in OBS (Tools -> WebSocket Server Settings)`);
          } finally {
            setIsObsConnecting(false);
          }
        }}
        aitobSettings={aitobSettings}
        onSaveAitobSettings={(newSettings) => {
          setAitobSettings(newSettings);
        }}
        onSyncAitob={() => {
          connectAitob(aitobSettings);
          addLog('AITOB', `Resyncing with ${aitobSettings.serverUrl}...`);
        }}
      />

      {/* Quick Setup Guide Modal */}
      <SetupGuideModal
        isOpen={isHelpModalOpen}
        onClose={() => setIsHelpModalOpen(false)}
      />

      {/* Trigger Editor Modal */}
      <TriggerEditorModal 
        isOpen={isTriggerModalOpen}
        onClose={() => setIsTriggerModalOpen(false)}
        onSave={handleSaveRule}
        onDelete={handleDeleteRule}
        initialRule={editingRule}
        defaultScope={triggerScope}
        currentTelemetry={{
          game: 'SF6',
          roundTimer,
          roundNumber,
          matchState,
          roomId,
          p1,
          p2,
          lastUpdated: Date.now()
        } as any}
      />
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import { TriggerRule, automationEngine } from '../services/automationEngine';
import { obsService } from '../services/obsService';
import { X, Save, Plus, RefreshCw, Trash2 } from 'lucide-react';

import { GameTelemetryData } from '../types/telemetry';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSave: (rule: TriggerRule) => void;
  onDelete?: (id: string) => void;
  initialRule?: TriggerRule;
  defaultScope?: 'MATCH' | 'P1' | 'P2';
  currentTelemetry?: GameTelemetryData;
}

export const TriggerEditorModal: React.FC<Props> = ({ isOpen, onClose, onSave, onDelete, initialRule, defaultScope = 'MATCH', currentTelemetry }) => {
  const generateId = () => 'rule_' + Math.random().toString(36).substr(2, 9);

  const [rule, setRule] = useState<TriggerRule>({
    id: generateId(),
    name: '',
    enabled: true,
    scope: defaultScope,
    variable: defaultScope === 'MATCH' ? 'ROUND_TIMER' : (defaultScope === 'P1' ? 'P1_DRIVE' : 'P2_DRIVE'),
    operator: '<=',
    threshold: 0,
    actionType: 'TOGGLE_SOURCE',
    sourceName: '',
    durationMode: 'WHILE_TRUE',
  });

  const [obsScenes, setObsScenes] = useState<string[]>([]);
  const [obsSources, setObsSources] = useState<string[]>([]);
  const [obsFilters, setObsFilters] = useState<string[]>([]);
  const [isLoadingObs, setIsLoadingObs] = useState(false);

  // Initial OBS Fetch
  useEffect(() => {
    if (isOpen && obsService.getConnected()) {
      setIsLoadingObs(true);
      obsService.getSceneList().then(scenes => {
        setObsScenes(scenes);
        setIsLoadingObs(false);
      });
    }
  }, [isOpen]);

  // Fetch sources when scene changes (or if no scene is selected, fetch for current scene)
  useEffect(() => {
    if (isOpen && obsService.getConnected()) {
      const targetScene = rule.sceneName || obsService.getCurrentScene();
      if (targetScene) {
        obsService.getSceneItemList(targetScene).then(setObsSources);
      }
    }
  }, [isOpen, rule.sceneName]);

  // Fetch filters when source changes
  useEffect(() => {
    if (isOpen && obsService.getConnected() && rule.sourceName && rule.actionType === 'TOGGLE_FILTER') {
      obsService.getSourceFilterList(rule.sourceName).then(setObsFilters);
    }
  }, [isOpen, rule.sourceName, rule.actionType]);

  useEffect(() => {
    if (initialRule) {
      setRule(initialRule);
    } else {
      setRule({
        id: generateId(),
        name: '',
        enabled: true,
        scope: defaultScope,
        variable: defaultScope === 'MATCH' ? 'ROUND_TIMER' : (defaultScope === 'P1' ? 'P1_DRIVE' : 'P2_DRIVE'),
        operator: '<=',
        threshold: 0,
        actionType: 'TOGGLE_SOURCE',
        sourceName: '',
        durationMode: 'WHILE_TRUE',
      });
    }
  }, [initialRule, defaultScope, isOpen]);

  if (!isOpen) return null;

  const handleSave = () => {
    if (!rule.name || !rule.sourceName) {
      alert('Please enter a rule name and OBS source name.');
      return;
    }
    onSave(rule);
    onClose();
  };

  const handleTest = () => {
    if (!rule.sourceName) {
      alert('Please enter an OBS source name to test.');
      return;
    }
    const fakeTelemetry: any = currentTelemetry || {
      p1: { displayName: 'P1_TEST', scoreInSet: 1, currentHp: 5000 },
      p2: { displayName: 'P2_TEST', scoreInSet: 0, currentHp: 10000 },
      roundTimer: 99,
      matchState: 'FIGHTING'
    };
    automationEngine.triggerAction(rule, true, fakeTelemetry);
    
    // Auto revert toggle after 3 seconds for safe testing
    if (rule.actionType !== 'UPDATE_TEXT') {
      setTimeout(() => {
        automationEngine.triggerAction(rule, false, fakeTelemetry);
      }, 3000);
    }
  };

  const variables = {
    MATCH: ['ALWAYS_TRUE', 'ROUND_TIMER', 'MATCH_STATE'],
    P1: ['P1_ROUNDS', 'P1_HP', 'P1_DRIVE', 'P1_SUPER', 'P1_COMBO', 'P1_DAMAGE', 'P1_PERFECT'],
    P2: ['P2_ROUNDS', 'P2_HP', 'P2_DRIVE', 'P2_SUPER', 'P2_COMBO', 'P2_DAMAGE', 'P2_PERFECT'],
  };

  const variableLabels: Record<string, string> = {
    'ROUND_TIMER': 'Round Timer (Seconds)',
    'MATCH_STATE': 'Match State (IDLE, ROUND_OVER...)',
    'P1_HP': 'P1 Health (HP)',
    'P1_DRIVE': 'P1 Drive Gauge',
    'P1_SUPER': 'P1 Super Art Level',
    'P1_COMBO': 'P1 Max Combo',
    'P1_DAMAGE': 'P1 Max Damage',
    'P1_PERFECT': 'P1 Perfect Round (1=Yes, 0=No)',
    'P1_ROUNDS': 'P1 Rounds Won',
    'P2_HP': 'P2 Health (HP)',
    'P2_DRIVE': 'P2 Drive Gauge',
    'P2_SUPER': 'P2 Super Art Level',
    'P2_COMBO': 'P2 Max Combo',
    'P2_DAMAGE': 'P2 Max Damage',
    'P2_PERFECT': 'P2 Perfect Round (1=Yes, 0=No)',
    'P2_ROUNDS': 'P2 Rounds Won',
    'ALWAYS_TRUE': 'Always Active (No Condition)',
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#0a0d14] border border-gray-700 rounded-2xl p-6 w-full max-w-2xl shadow-[0_0_40px_rgba(0,0,0,0.5)]">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-rajdhani font-bold text-white flex items-center gap-2">
            <Plus className="text-cyan-500 w-5 h-5" />
            {initialRule ? 'Edit Trigger' : 'New Trigger'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Left Column: Condition */}
          <div className="space-y-4 border-r border-gray-800 pr-6">
            <h3 className="text-sm text-cyan-400 font-bold uppercase tracking-wider mb-2">1. Condition</h3>
            
            <div>
              <label className="block text-xs text-gray-400 mb-1">Rule Name</label>
              <input 
                type="text" 
                value={rule.name}
                onChange={e => setRule({...rule, name: e.target.value})}
                placeholder="e.g., Burnout Warning"
                className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-sm text-white focus:border-cyan-500 outline-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Scope</label>
                <select 
                  value={rule.scope}
                  onChange={e => {
                    const newScope = e.target.value as 'MATCH'|'P1'|'P2';
                    setRule({...rule, scope: newScope, variable: variables[newScope][0] as any});
                  }}
                  className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-sm text-white outline-none"
                >
                  <option value="MATCH">Match Center</option>
                  <option value="P1">Player 1</option>
                  <option value="P2">Player 2</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Variable</label>
                <select 
                  value={rule.variable}
                  onChange={e => setRule({...rule, variable: e.target.value as any})}
                  className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-sm text-white outline-none"
                >
                  {variables[rule.scope].map(v => <option key={v} value={v}>{variableLabels[v] || v}</option>)}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Operator</label>
                <select 
                  value={rule.operator}
                  onChange={e => setRule({...rule, operator: e.target.value as any})}
                  className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-sm text-white outline-none font-mono font-bold text-center"
                >
                  <option value="==">== (Equals)</option>
                  <option value="<">&lt; (Less than)</option>
                  <option value="<=">&lt;= (Less or equal)</option>
                  <option value=">">&gt; (Greater than)</option>
                  <option value=">=">&gt;= (Greater or equal)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Threshold</label>
                <input 
                  type="text" 
                  value={rule.threshold}
                  onChange={e => setRule({...rule, threshold: isNaN(Number(e.target.value)) ? e.target.value : Number(e.target.value)})}
                  className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-sm text-white focus:border-cyan-500 outline-none font-mono"
                />
              </div>
            </div>
          </div>

          {/* Right Column: Action & Duration */}
          <div className="space-y-4">
            <h3 className="text-sm text-rose-400 font-bold uppercase tracking-wider mb-2">2. Action</h3>

            <div>
              <label className="block text-xs text-gray-400 mb-1">Action Type</label>
              <select 
                value={rule.actionType}
                onChange={e => setRule({...rule, actionType: e.target.value as any})}
                className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-sm text-white outline-none"
              >
                <option value="TOGGLE_SOURCE">Toggle Source</option>
                <option value="TOGGLE_FILTER">Toggle Filter</option>
                <option value="UPDATE_TEXT">Update Text Source</option>
              </select>
            </div>

            {rule.actionType === 'TOGGLE_SOURCE' && (
              <div>
                <label className="block text-xs text-gray-400 mb-1">OBS Scene Name (Optional)</label>
                {obsScenes.length > 0 ? (
                  <select
                    value={rule.sceneName || ''}
                    onChange={e => setRule({...rule, sceneName: e.target.value})}
                    className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-sm text-white focus:border-rose-500 outline-none"
                  >
                    <option value="">[Current Active Scene]</option>
                    {obsScenes.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                ) : (
                  <input 
                    type="text" 
                    value={rule.sceneName || ''}
                    onChange={e => setRule({...rule, sceneName: e.target.value})}
                    placeholder="e.g., SF6_Gameplay (Leave empty for current)"
                    className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-sm text-white focus:border-rose-500 outline-none"
                  />
                )}
              </div>
            )}

            <div>
              <label className="block text-xs text-gray-400 mb-1">OBS Source Name (Required)</label>
              {obsSources.length > 0 ? (
                <select
                  value={rule.sourceName}
                  onChange={e => setRule({...rule, sourceName: e.target.value})}
                  className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-sm text-white focus:border-rose-500 outline-none"
                >
                  <option value="" disabled>-- Select Source --</option>
                  {obsSources.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              ) : (
                <input 
                  type="text" 
                  value={rule.sourceName}
                  onChange={e => setRule({...rule, sourceName: e.target.value})}
                  placeholder="e.g., P1_Camera"
                  className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-sm text-white focus:border-rose-500 outline-none"
                />
              )}
            </div>

            {rule.actionType === 'TOGGLE_FILTER' && (
              <div>
                <label className="block text-xs text-gray-400 mb-1">OBS Filter Name (Required)</label>
                {obsFilters.length > 0 ? (
                  <select
                    value={rule.filterName || ''}
                    onChange={e => setRule({...rule, filterName: e.target.value})}
                    className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-sm text-white focus:border-rose-500 outline-none"
                  >
                    <option value="" disabled>-- Select Filter --</option>
                    {obsFilters.map(f => <option key={f} value={f}>{f}</option>)}
                  </select>
                ) : (
                  <input 
                    type="text" 
                    value={rule.filterName || ''}
                    onChange={e => setRule({...rule, filterName: e.target.value})}
                    placeholder="e.g., ColorCorrection_Red"
                    className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-sm text-white focus:border-rose-500 outline-none"
                  />
                )}
              </div>
            )}

            {rule.actionType === 'UPDATE_TEXT' && (
              <div>
                <div className="flex justify-between items-end mb-1">
                  <label className="block text-xs text-gray-400">Text Template</label>
                  <select 
                    onChange={e => {
                      if (!e.target.value) return;
                      const text = rule.textContent || '';
                      setRule({...rule, textContent: text + e.target.value});
                      e.target.value = '';
                    }}
                    className="bg-gray-800 text-xs text-cyan-400 border border-gray-700 rounded px-1 outline-none font-bold max-w-[120px]"
                  >
                    <option value="">+ Variable</option>
                    <optgroup label="Match">
                      <option value="[Match_State]">[Match_State]</option>
                      <option value="[Round_Timer]">[Round_Timer]</option>
                    </optgroup>
                    <optgroup label="Player 1">
                      <option value="[P1_Name]">[P1_Name]</option>
                      <option value="[P1_Character]">[P1_Character]</option>
                      <option value="[P1_Score]">[P1_Score]</option>
                      <option value="[P1_Rounds]">[P1_Rounds]</option>
                      <option value="[P1_HP]">[P1_HP]</option>
                    </optgroup>
                    <optgroup label="Player 2">
                      <option value="[P2_Name]">[P2_Name]</option>
                      <option value="[P2_Character]">[P2_Character]</option>
                      <option value="[P2_Score]">[P2_Score]</option>
                      <option value="[P2_Rounds]">[P2_Rounds]</option>
                      <option value="[P2_HP]">[P2_HP]</option>
                    </optgroup>
                  </select>
                </div>
                <textarea 
                  value={rule.textContent || ''}
                  onChange={e => setRule({...rule, textContent: e.target.value})}
                  placeholder="e.g., [P1_Name] | [P1_Score] - [P2_Score] | [P2_Name]"
                  className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-sm text-white focus:border-rose-500 outline-none h-16 resize-none font-mono"
                />
              </div>
            )}

            <div className="pt-2">
              <label className="block text-xs text-gray-400 mb-1">Duration Mode</label>
              <div className="flex gap-1.5">
                <button 
                  onClick={() => setRule({...rule, durationMode: 'WHILE_TRUE'})}
                  className={`flex-1 p-2 rounded text-[11px] font-bold transition border ${rule.durationMode === 'WHILE_TRUE' ? 'bg-violet-600 border-violet-500 text-white shadow-lg' : 'bg-gray-900 border-gray-700 text-gray-400 hover:border-gray-500'}`}
                >
                  While True
                </button>
                <button 
                  onClick={() => setRule({...rule, durationMode: 'UNTIL_ROUND_END'})}
                  className={`flex-1 p-2 rounded text-[11px] font-bold transition border ${rule.durationMode === 'UNTIL_ROUND_END' ? 'bg-violet-600 border-violet-500 text-white shadow-lg' : 'bg-gray-900 border-gray-700 text-gray-400 hover:border-gray-500'}`}
                >
                  Until Round End
                </button>
                <button 
                  onClick={() => setRule({...rule, durationMode: 'FIXED_TIME', durationSeconds: rule.durationSeconds || 5})}
                  className={`flex-1 p-2 rounded text-[11px] font-bold transition border ${rule.durationMode === 'FIXED_TIME' ? 'bg-violet-600 border-violet-500 text-white shadow-lg' : 'bg-gray-900 border-gray-700 text-gray-400 hover:border-gray-500'}`}
                >
                  Fixed Time
                </button>
              </div>
            </div>

            {rule.durationMode === 'FIXED_TIME' && (
              <div className="flex items-center gap-2 mt-2">
                <input 
                  type="number" 
                  value={rule.durationSeconds || 5}
                  onChange={e => setRule({...rule, durationSeconds: Number(e.target.value)})}
                  className="w-20 bg-gray-900 border border-gray-700 rounded p-2 text-sm text-white focus:border-violet-500 outline-none text-center"
                />
                <span className="text-xs text-gray-400">Seconds</span>
              </div>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="mt-8 flex justify-between gap-3 border-t border-gray-800 pt-4">
          <div className="flex gap-3">
            <button 
              onClick={handleTest}
              className="flex items-center gap-2 px-5 py-2 bg-gray-800 hover:bg-gray-700 rounded font-bold text-sm text-cyan-400 border border-gray-700 transition shadow"
              title="Triggers the action immediately. (Toggles revert after 3 seconds)"
            >
              <RefreshCw className="w-4 h-4" /> Test Action
            </button>

            {initialRule && onDelete && (
              <button 
                onClick={() => {
                  if (confirm('Are you sure you want to delete this trigger?')) {
                    onDelete(initialRule.id);
                  }
                }}
                className="flex items-center gap-2 px-4 py-2 bg-rose-900/30 hover:bg-rose-900/60 text-rose-500 rounded font-bold text-sm border border-rose-900/50 transition"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
          
          <div className="flex gap-3">
            <button onClick={onClose} className="px-5 py-2 rounded font-bold text-sm text-gray-400 hover:text-white transition">
              Cancel
            </button>
            <button onClick={handleSave} className="flex items-center gap-2 px-6 py-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 rounded font-bold text-sm text-white shadow-lg transition">
              <Save className="w-4 h-4" /> Save Trigger
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

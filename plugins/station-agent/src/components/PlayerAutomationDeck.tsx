import React, { useState } from 'react';
import { TriggerRule } from '../services/automationEngine';
import { Shield, Settings, Power, Plus, Copy, ChevronUp, ChevronDown, GripVertical } from 'lucide-react';

interface Props {
  playerNumber: 1 | 2;
  rules: TriggerRule[];
  onToggleRule: (id: string) => void;
  onEditRule: (id: string) => void;
  onAddRule: (scope: 'P1' | 'P2') => void;
  onMirrorRule?: (id: string) => void;
  onMoveRule?: (id: string, direction: 'UP' | 'DOWN') => void;
  onReorderRules?: (draggedId: string, targetId: string) => void;
}

export const PlayerAutomationDeck: React.FC<Props> = ({ 
  playerNumber, 
  rules, 
  onToggleRule, 
  onEditRule, 
  onAddRule, 
  onMirrorRule,
  onMoveRule,
  onReorderRules
}) => {
  const playerRules = rules.filter(r => r.scope === (playerNumber === 1 ? 'P1' : 'P2'));
  const isP1 = playerNumber === 1;
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);

  if (playerRules.length === 0) return null;

  const handleDragStart = (e: React.DragEvent, id: string) => {
    e.dataTransfer.setData('text/plain', id);
    setDraggedId(id);
  };

  const handleDragOver = (e: React.DragEvent, id: string) => {
    e.preventDefault();
    if (dragOverId !== id) {
      setDragOverId(id);
    }
  };

  const handleDrop = (e: React.DragEvent, targetId: string) => {
    e.preventDefault();
    const sourceId = e.dataTransfer.getData('text/plain') || draggedId;
    if (sourceId && sourceId !== targetId && onReorderRules) {
      onReorderRules(sourceId, targetId);
    }
    setDraggedId(null);
    setDragOverId(null);
  };

  const handleDragEnd = () => {
    setDraggedId(null);
    setDragOverId(null);
  };

  return (
    <div className={`mt-4 glass-panel p-3 rounded-xl border ${isP1 ? 'border-cyan-900/30' : 'border-rose-900/30'}`}>
      <div className="flex items-center justify-between mb-3 px-1 border-b border-gray-800 pb-2">
        <div className="flex items-center gap-2 text-xs text-gray-400 font-rajdhani uppercase tracking-widest">
          <Shield className={`w-3.5 h-3.5 ${isP1 ? 'text-cyan-500' : 'text-rose-500'}`} />
          P{playerNumber} Triggers ({playerRules.length})
        </div>
        <button 
          onClick={() => onAddRule(isP1 ? 'P1' : 'P2')}
          className={`p-1 rounded hover:bg-gray-800 transition ${isP1 ? 'text-cyan-500' : 'text-rose-500'}`}
          title="Add Trigger"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>
      
      <div className="space-y-1.5">
        {playerRules.map((rule, idx) => {
          const isDragging = draggedId === rule.id;
          const isOver = dragOverId === rule.id;
          const isFirst = idx === 0;
          const isLast = idx === playerRules.length - 1;

          return (
            <div 
              key={rule.id}
              draggable
              onDragStart={(e) => handleDragStart(e, rule.id)}
              onDragOver={(e) => handleDragOver(e, rule.id)}
              onDrop={(e) => handleDrop(e, rule.id)}
              onDragEnd={handleDragEnd}
              className={`flex items-center justify-between bg-black/40 p-2 rounded-lg border transition-all ${
                isDragging 
                  ? 'opacity-40 border-cyan-500/50 dashed' 
                  : isOver 
                    ? 'border-cyan-400 bg-cyan-950/20' 
                    : 'border-gray-800/60 hover:border-gray-700'
              }`}
            >
              <div className="flex items-center gap-2 flex-1 min-w-0">
                {/* Drag Handle & Reorder Arrows */}
                <div className="flex items-center text-gray-600 hover:text-gray-400 cursor-grab active:cursor-grabbing">
                  <GripVertical className="w-3.5 h-3.5" />
                </div>

                <div className="flex flex-col min-w-0 pr-2">
                  <span className="text-xs text-gray-200 font-bold truncate">{rule.name}</span>
                  <span className="text-[10px] text-gray-500 font-mono">
                    {rule.variable} {rule.operator} {rule.threshold}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                {/* Move Up / Down Buttons */}
                {onMoveRule && (
                  <div className="flex flex-col -space-y-1 mr-1">
                    <button
                      type="button"
                      disabled={isFirst}
                      onClick={() => onMoveRule(rule.id, 'UP')}
                      className={`p-0.5 rounded hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition ${isFirst ? 'opacity-20 cursor-not-allowed' : ''}`}
                      title="Move Up"
                    >
                      <ChevronUp className="w-3 h-3" />
                    </button>
                    <button
                      type="button"
                      disabled={isLast}
                      onClick={() => onMoveRule(rule.id, 'DOWN')}
                      className={`p-0.5 rounded hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition ${isLast ? 'opacity-20 cursor-not-allowed' : ''}`}
                      title="Move Down"
                    >
                      <ChevronDown className="w-3 h-3" />
                    </button>
                  </div>
                )}

                {onMirrorRule && (
                  <button 
                    onClick={() => onMirrorRule(rule.id)}
                    className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                    title={isP1 ? "Mirror to P2" : "Mirror to P1"}
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                )}
                <button 
                  onClick={() => onEditRule(rule.id)}
                  className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                  title="Edit Rule"
                >
                  <Settings className="w-3.5 h-3.5" />
                </button>
                <button 
                  onClick={() => onToggleRule(rule.id)}
                  className={`p-1.5 rounded-lg transition-colors ${rule.enabled ? (isP1 ? 'bg-cyan-500/20 text-cyan-400' : 'bg-rose-500/20 text-rose-400') : 'bg-gray-800 text-gray-500 hover:text-gray-300'}`}
                  title={rule.enabled ? 'Disable' : 'Enable'}
                >
                  <Power className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

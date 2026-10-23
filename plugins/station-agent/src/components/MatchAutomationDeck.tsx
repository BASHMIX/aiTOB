import React, { useState } from 'react';
import { TriggerRule } from '../services/automationEngine';
import { Power, Zap, Settings, Plus, ChevronUp, ChevronDown, GripVertical } from 'lucide-react';

interface Props {
  rules: TriggerRule[];
  onToggleRule: (id: string) => void;
  onEditRule: (id: string) => void;
  onAddRule: (scope: 'MATCH') => void;
  onMoveRule?: (id: string, direction: 'UP' | 'DOWN') => void;
  onReorderRules?: (draggedId: string, targetId: string) => void;
}

export const MatchAutomationDeck: React.FC<Props> = ({ 
  rules, 
  onToggleRule, 
  onEditRule, 
  onAddRule,
  onMoveRule,
  onReorderRules
}) => {
  const matchRules = rules.filter(r => r.scope === 'MATCH');
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);

  if (matchRules.length === 0) return null;

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
    <div className="mt-4 glass-panel p-3 rounded-xl border border-violet-900/30">
      <div className="flex items-center justify-between mb-3 px-1 border-b border-gray-800 pb-2">
        <div className="flex items-center gap-2 text-xs text-gray-400 font-rajdhani uppercase tracking-widest">
          <Zap className="w-3.5 h-3.5 text-violet-500" />
          Match Triggers ({matchRules.length})
        </div>
        <button 
          onClick={() => onAddRule('MATCH')}
          className="p-1 rounded hover:bg-gray-800 transition text-violet-500"
          title="Add Trigger"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>
      
      <div className="space-y-1.5">
        {matchRules.map((rule, idx) => {
          const isDragging = draggedId === rule.id;
          const isOver = dragOverId === rule.id;
          const isFirst = idx === 0;
          const isLast = idx === matchRules.length - 1;

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
                  ? 'opacity-40 border-violet-500/50 dashed' 
                  : isOver 
                    ? 'border-violet-400 bg-violet-950/20' 
                    : 'border-gray-800/60 hover:border-gray-700'
              }`}
            >
              <div className="flex items-center gap-2 flex-1 min-w-0">
                {/* Drag Handle */}
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

                <button 
                  onClick={() => onEditRule(rule.id)}
                  className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                  title="Edit Rule"
                >
                  <Settings className="w-3.5 h-3.5" />
                </button>
                <button 
                  onClick={() => onToggleRule(rule.id)}
                  className={`p-1.5 rounded-lg transition-colors ${rule.enabled ? 'bg-violet-500/20 text-violet-400' : 'bg-gray-800 text-gray-500 hover:text-gray-300'}`}
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

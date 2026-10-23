import React from 'react';
import { 
  Send, 
  CheckCircle2, 
  RotateCcw, 
  Sparkles, 
  Tv2, 
  Flame,
  Check,
  AlertCircle
} from 'lucide-react';

interface ControlDeckProps {
  onSendGameInvite: () => void;
  onSubmitResult: () => void;
  onResetSet: () => void;
  autoConfirm: boolean;
  onToggleAutoConfirm: () => void;
  autoObsSwitch: boolean;
  onToggleAutoObsSwitch: () => void;
  isSubmitting: boolean;
  submitMessage: { type: 'success' | 'error'; text: string } | null;
}

export const ControlDeck: React.FC<ControlDeckProps> = ({
  onSendGameInvite,
  onSubmitResult,
  onResetSet,
  autoConfirm,
  onToggleAutoConfirm,
  autoObsSwitch,
  onToggleAutoObsSwitch,
  isSubmitting,
  submitMessage,
}) => {
  return (
    <footer className="glass-panel border-t border-slate-800/80 p-5 mt-auto">
      {/* Toast Alert / Status Message if present */}
      {submitMessage && (
        <div 
          className={`mb-4 p-3 rounded-xl border flex items-center justify-between animate-fadeIn text-sm ${
            submitMessage.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
          }`}
        >
          <div className="flex items-center gap-2">
            {submitMessage.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-400" />
            )}
            <span>{submitMessage.text}</span>
          </div>
        </div>
      )}

      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Left Side: Automation Toggles */}
        <div className="flex items-center gap-4 w-full md:w-auto">
          {/* Auto-Confirm Result Toggle */}
          <label className="flex items-center gap-2.5 cursor-pointer bg-[#090d16] px-3.5 py-2 rounded-xl border border-slate-800 hover:border-slate-700 transition">
            <div className="relative">
              <input
                type="checkbox"
                checked={autoConfirm}
                onChange={onToggleAutoConfirm}
                className="sr-only"
              />
              <div 
                className={`w-10 h-5.5 rounded-full transition-colors flex items-center p-0.5 ${
                  autoConfirm ? 'bg-cyan-500 justify-end' : 'bg-slate-700 justify-start'
                }`}
              >
                <div className="w-4.5 h-4.5 bg-white rounded-full shadow-md" />
              </div>
            </div>
            <div className="flex flex-col text-right">
              <span className="text-xs font-bold text-slate-200 flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                Auto Confirm
              </span>
              <span className="text-[10px] text-slate-400">
                Send results immediately when set ends
              </span>
            </div>
          </label>

          {/* Auto OBS Scene Switcher Toggle */}
          <label className="flex items-center gap-2.5 cursor-pointer bg-[#090d16] px-3.5 py-2 rounded-xl border border-slate-800 hover:border-slate-700 transition">
            <div className="relative">
              <input
                type="checkbox"
                checked={autoObsSwitch}
                onChange={onToggleAutoObsSwitch}
                className="sr-only"
              />
              <div 
                className={`w-10 h-5.5 rounded-full transition-colors flex items-center p-0.5 ${
                  autoObsSwitch ? 'bg-purple-500 justify-end' : 'bg-slate-700 justify-start'
                }`}
              >
                <div className="w-4.5 h-4.5 bg-white rounded-full shadow-md" />
              </div>
            </div>
            <div className="flex flex-col text-right">
              <span className="text-xs font-bold text-slate-200 flex items-center gap-1">
                <Tv2 className="w-3.5 h-3.5 text-purple-400" />
                Auto Switch OBS Scenes
              </span>
              <span className="text-[10px] text-slate-400">
                Gameplay / PreMatch / Winner
              </span>
            </div>
          </label>
        </div>

        {/* Right Side: Primary Action Buttons */}
        <div className="flex items-center gap-3 w-full md:w-auto justify-end">
          {/* Reset Set */}
          <button
            onClick={onResetSet}
            className="p-2.5 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-white border border-slate-700 transition"
            title="Reset Rounds and Scores"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          {/* Send In-Game Invite */}
          <button
            onClick={onSendGameInvite}
            className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 hover:border-slate-600 font-bold text-xs flex items-center gap-2 transition active:scale-95 shadow-md"
          >
            <Send className="w-4 h-4 text-cyan-400" />
            <span>Send In-Game Invite</span>
          </button>

          {/* Confirm & Submit Result to aiTOB Platform */}
          <button
            onClick={onSubmitResult}
            disabled={isSubmitting}
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-extrabold text-sm flex items-center gap-2 transition active:scale-95 shadow-lg shadow-blue-500/25 disabled:opacity-50"
          >
            {isSubmitting ? (
              <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
            ) : (
              <Check className="w-4 h-4 stroke-[3]" />
            )}
            <span>Submit Result to aiTOB</span>
          </button>
        </div>
      </div>
    </footer>
  );
};

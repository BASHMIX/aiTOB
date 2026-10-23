import React, { useState } from 'react';
import { X, HelpCircle, Gamepad2, Video, Globe2, ExternalLink, CheckCircle } from 'lucide-react';

interface SetupGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SetupGuideModal: React.FC<SetupGuideModalProps> = ({ isOpen, onClose }) => {
  const [activeStep, setActiveStep] = useState<'SF6' | 'OBS' | 'AITOB'>('SF6');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fadeIn">
      <div className="w-full max-w-2xl bg-[#0d111a] border border-gray-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-[#090d14]">
          <div className="flex items-center gap-2">
            <HelpCircle className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-bold text-white font-rajdhani tracking-wider">Station Agent Setup Guide</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white bg-gray-800/60 hover:bg-gray-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Step Navigation */}
        <div className="flex border-b border-gray-800 bg-[#080b12]">
          <button
            onClick={() => setActiveStep('SF6')}
            className={`flex-1 py-3 px-4 text-xs font-bold flex items-center justify-center gap-2 border-b-2 transition ${
              activeStep === 'SF6'
                ? 'border-indigo-500 text-indigo-300 bg-indigo-500/5'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            <Gamepad2 className="w-4 h-4" />
            1. Street Fighter 6 Mod
          </button>
          <button
            onClick={() => setActiveStep('OBS')}
            className={`flex-1 py-3 px-4 text-xs font-bold flex items-center justify-center gap-2 border-b-2 transition ${
              activeStep === 'OBS'
                ? 'border-purple-500 text-purple-300 bg-purple-500/5'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            <Video className="w-4 h-4" />
            2. OBS Studio WebSocket
          </button>
          <button
            onClick={() => setActiveStep('AITOB')}
            className={`flex-1 py-3 px-4 text-xs font-bold flex items-center justify-center gap-2 border-b-2 transition ${
              activeStep === 'AITOB'
                ? 'border-cyan-500 text-cyan-300 bg-cyan-500/5'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            <Globe2 className="w-4 h-4" />
            3. Tournament Platform
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-4 text-xs text-gray-300 leading-relaxed bg-[#0b0f19]">
          
          {activeStep === 'SF6' && (
            <div className="space-y-4 animate-fadeIn">
              <div className="p-3 bg-indigo-950/30 border border-indigo-800/40 rounded-xl text-indigo-200">
                <span className="font-bold block mb-1">🎮 Real-Time In-Game Telemetry:</span>
                The Station Agent reads live health bars, drive gauge, rounds, super art, and match states directly from Street Fighter 6 memory safely via REFramework.
              </div>

              <div className="space-y-3">
                <div className="flex items-start gap-2.5">
                  <span className="w-5 h-5 rounded-full bg-indigo-600/30 text-indigo-400 flex items-center justify-center shrink-0 font-bold text-[11px]">1</span>
                  <div>
                    <span className="font-semibold text-white">Install REFramework:</span>
                    <p className="text-gray-400 mt-0.5">
                      Ensure <span className="font-mono text-cyan-300">dinput8.dll</span> (REFramework for SF6) is in your main Street Fighter 6 folder.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <span className="w-5 h-5 rounded-full bg-indigo-600/30 text-indigo-400 flex items-center justify-center shrink-0 font-bold text-[11px]">2</span>
                  <div>
                    <span className="font-semibold text-white">Install the aiTOB Lua Script:</span>
                    <p className="text-gray-400 mt-0.5">
                      Open <strong className="text-white">Settings -&gt; Game & Mod</strong>, select your SF6 folder, and click <strong className="text-emerald-400">Install Mod</strong>. It automatically copies the telemetry script into <span className="font-mono text-cyan-300">reframework/autorun/</span>.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <span className="w-5 h-5 rounded-full bg-indigo-600/30 text-indigo-400 flex items-center justify-center shrink-0 font-bold text-[11px]">3</span>
                  <div>
                    <span className="font-semibold text-white">Start the Game:</span>
                    <p className="text-gray-400 mt-0.5">
                      Launch SF6. The status badge will turn <span className="text-emerald-400 font-bold">Game Connected</span> and packet counters will tick up live!
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeStep === 'OBS' && (
            <div className="space-y-4 animate-fadeIn">
              <div className="p-3 bg-purple-950/30 border border-purple-800/40 rounded-xl text-purple-200">
                <span className="font-bold block mb-1">🎥 Automated Broadcast & Production:</span>
                Switch scenes seamlessly between Versus, InGame, and Victory without touching OBS during tournament sets.
              </div>

              <div className="space-y-3">
                <div className="flex items-start gap-2.5">
                  <span className="w-5 h-5 rounded-full bg-purple-600/30 text-purple-400 flex items-center justify-center shrink-0 font-bold text-[11px]">1</span>
                  <div>
                    <span className="font-semibold text-white">Enable WebSocket Server in OBS:</span>
                    <p className="text-gray-400 mt-0.5">
                      In OBS Studio, navigate to <span className="text-white font-semibold">Tools -&gt; WebSocket Server Settings</span> and check <span className="text-white font-semibold">"Enable WebSocket server"</span> (Default Server Port: 4455).
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <span className="w-5 h-5 rounded-full bg-purple-600/30 text-purple-400 flex items-center justify-center shrink-0 font-bold text-[11px]">2</span>
                  <div>
                    <span className="font-semibold text-white">Match Scene Names:</span>
                    <p className="text-gray-400 mt-0.5">
                      Set up your scenes in OBS (e.g. <span className="font-mono text-purple-300">SF6 - Versus</span>, <span className="font-mono text-purple-300">SF6 - InGame</span>, <span className="font-mono text-purple-300">SF6 - Victory</span>), or adjust the names in Station Agent settings to match your existing OBS layout.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <span className="w-5 h-5 rounded-full bg-purple-600/30 text-purple-400 flex items-center justify-center shrink-0 font-bold text-[11px]">3</span>
                  <div>
                    <span className="font-semibold text-white">Connect:</span>
                    <p className="text-gray-400 mt-0.5">
                      Click <strong className="text-purple-400">Test OBS Connection</strong> in Settings. Once connected, your triggers and scene transitions will execute automatically!
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeStep === 'AITOB' && (
            <div className="space-y-4 animate-fadeIn">
              <div className="p-3 bg-cyan-950/30 border border-cyan-800/40 rounded-xl text-cyan-200">
                <span className="font-bold block mb-1">🌐 Tournament Station Synchronization:</span>
                Connects physical tournament gaming stations to the central tournament bracket manager.
              </div>

              <div className="space-y-3">
                <div className="flex items-start gap-2.5">
                  <span className="w-5 h-5 rounded-full bg-cyan-600/30 text-cyan-400 flex items-center justify-center shrink-0 font-bold text-[11px]">1</span>
                  <div>
                    <span className="font-semibold text-white">Station ID:</span>
                    <p className="text-gray-400 mt-0.5">
                      Assign a station name (e.g. <span className="font-mono text-cyan-300">station-01</span>, <span className="font-mono text-cyan-300">main-stream</span>).
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <span className="w-5 h-5 rounded-full bg-cyan-600/30 text-cyan-400 flex items-center justify-center shrink-0 font-bold text-[11px]">2</span>
                  <div>
                    <span className="font-semibold text-white">Automated Match Verification:</span>
                    <p className="text-gray-400 mt-0.5">
                      When a match concludes, the verified score and winner are submitted directly to the tournament bracket with one click or full auto-confirmation.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-gray-800 bg-[#090d14] flex items-center justify-between text-[11px] text-gray-500">
          <div className="flex items-center gap-3">
            <a href="https://aitob.bashtech.xyz/terms#station-agent" target="_blank" rel="noopener noreferrer" className="hover:text-cyan-400 underline">
              Station Agent EULA
            </a>
            <span>•</span>
            <a href="https://aitob.bashtech.xyz/privacy" target="_blank" rel="noopener noreferrer" className="hover:text-cyan-400 underline">
              Privacy Policy
            </a>
          </div>
          <button
            onClick={onClose}
            className="px-5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition"
          >
            Got It!
          </button>
        </div>

      </div>
    </div>
  );
};

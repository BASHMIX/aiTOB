import { useState, useRef } from 'react';
import { Save, Edit3, Check, X, Image as ImageIcon, Link as LinkIcon, Undo, Redo, Download, Upload, ChevronDown } from 'lucide-react';
import axios from 'axios';
import { useEditorStore } from '@/store/useEditorStore';
import { waitForOverlayCanvasAssets } from '@/utils/overlayAssets';

interface TopBarProps {
  slot: string;
  stationId: string;
  onRename: (newName: string) => void;
  onSave: () => void;
  onLoadClick: () => void;
  status: string;
  onExportSlide?: () => void;
  onExportPackage?: () => void;
  onImportFile?: (file: File) => void;
}

export function TopBar({
  slot,
  stationId,
  onRename,
  onSave,
  onLoadClick,
  status,
  onExportSlide,
  onExportPackage,
  onImportFile,
}: TopBarProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [newName, setNewName] = useState(slot);
  const [isPreparingSlide, setIsPreparingSlide] = useState(false);
  const [isExportMenuOpen, setIsExportMenuOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const store = useEditorStore();

  const handleRename = () => {
    onRename(newName);
    setIsEditing(false);
  };

  const copyOBSLink = async () => {
    try {
      const response = await axios.post(`/api/stations/${stationId}/overlay-access`);
      const obsUrl = `${window.location.origin}${response.data.url}`;
      await navigator.clipboard.writeText(obsUrl);
      alert('Station Browser Source link copied. It follows the station active slide.');
    } catch {
      alert('The station Browser Source link could not be created.');
    }
  };

  const playSlide = async () => {
    if (isPreparingSlide) return;
    setIsPreparingSlide(true);
    try {
      const canvas = document.querySelector<HTMLElement>('[data-overlay-canvas="true"]');
      await waitForOverlayCanvasAssets(canvas, store.background_url);
      window.dispatchEvent(new Event('play-slide-preview'));
    } finally {
      setIsPreparingSlide(false);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && onImportFile) {
      onImportFile(file);
      e.target.value = '';
    }
  };

  return (
    <div className="h-16 bg-[#2a2a2a] border-b border-white/10 flex items-center justify-between px-6 z-50">
      {/* Hidden file input for quick import */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".json,.aitob-overlay.json,.aitob-package.json"
        className="hidden"
        onChange={handleFileInputChange}
      />

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          {isEditing ? (
            <div className="flex items-center gap-1">
              <input 
                value={newName}
                onChange={e => setNewName(e.target.value)}
                className="bg-[#111] border border-accentYellow/50 rounded px-2 py-1 text-sm text-white focus:outline-none"
                autoFocus
              />
              <button onClick={handleRename} className="p-1 hover:text-statusGreen"><Check size={16} /></button>
              <button onClick={() => { setIsEditing(false); setNewName(slot); }} className="p-1 hover:text-red-400"><X size={16} /></button>
            </div>
          ) : (
            <div className="flex items-center gap-2 group min-w-[180px]">
              <h1 className="text-lg font-bold tracking-tight text-white/90">
                Overlay: <span className="text-accentYellow">{slot}</span>
              </h1>
              <button 
                onClick={() => setIsEditing(true)}
                className="opacity-0 group-hover:opacity-100 p-1 text-white/40 hover:text-white transition-all"
              >
                <Edit3 size={14} />
              </button>
            </div>
          )}
        </div>

        <div className="h-6 w-px bg-white/10 mx-1" />

        {/* Undo / Redo controls */}
        <div className="flex items-center gap-1 bg-[#1a1a1a] rounded-full p-1 border border-white/5">
          <button 
            onClick={() => store.undo()} 
            disabled={store.past.length === 0}
            className={`p-1.5 rounded-full hover:bg-white/10 transition-colors ${store.past.length === 0 ? 'text-white/20 cursor-not-allowed' : 'text-[#00ffcc] hover:text-white'}`}
            title="Undo"
          >
            <Undo size={14} />
          </button>
          <button 
            onClick={() => store.redo()} 
            disabled={store.future.length === 0}
            className={`p-1.5 rounded-full hover:bg-white/10 transition-colors ${store.future.length === 0 ? 'text-white/20 cursor-not-allowed' : 'text-[#00ffcc] hover:text-white'}`}
            title="Redo"
          >
            <Redo size={14} />
          </button>
        </div>

        <button 
          onClick={playSlide}
          disabled={isPreparingSlide}
          className="flex items-center gap-2 bg-[#00ffcc]/20 hover:bg-[#00ffcc]/30 text-[#00ffcc] border border-[#00ffcc]/40 px-4 py-1.5 rounded-full text-sm font-bold transition-all hover:scale-105 active:scale-95 whitespace-nowrap"
          title="Play PowerPoint slide animation sequence for all elements"
        >
          {isPreparingSlide ? 'Preparing Images…' : '▶ Play Slide'}
        </button>

        <button 
          onClick={copyOBSLink}
          className="flex items-center gap-2 bg-accentYellow/20 hover:bg-accentYellow/30 text-accentYellow border border-accentYellow/40 px-4 py-1.5 rounded-full text-sm font-bold transition-all hover:scale-105 active:scale-95 whitespace-nowrap"
          title="Copy revocable Browser Source link for the full station slideshow"
        >
          <LinkIcon size={16} />
          Copy OBS Link
        </button>

        <button 
          onClick={onLoadClick}
          className="flex items-center gap-2 bg-[#333] hover:bg-[#444] text-white border border-white/20 px-4 py-1.5 rounded-full text-sm font-bold transition-all hover:scale-105 active:scale-95 whitespace-nowrap"
          title="Load saved slides or browse template gallery"
        >
          <ImageIcon size={16} />
          Load Slide
        </button>

        {/* Quick Import Button */}
        {onImportFile && (
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-2 bg-[#1a1a1a] hover:bg-[#333] text-white/90 hover:text-white border border-white/20 px-3.5 py-1.5 rounded-full text-sm font-bold transition-all hover:scale-105 active:scale-95 whitespace-nowrap"
            title="Import overlay or package from a JSON file"
          >
            <Upload size={15} className="text-[#00ffcc]" />
            Import
          </button>
        )}

        {/* Quick Export Dropdown */}
        {(onExportSlide || onExportPackage) && (
          <div className="relative">
            <button
              onClick={() => setIsExportMenuOpen((prev) => !prev)}
              className="flex items-center gap-1.5 bg-[#1a1a1a] hover:bg-[#333] text-white/90 hover:text-white border border-white/20 px-3.5 py-1.5 rounded-full text-sm font-bold transition-all hover:scale-105 active:scale-95 whitespace-nowrap"
              title="Export overlay or station package"
            >
              <Download size={15} className="text-accentYellow" />
              Export
              <ChevronDown size={14} className="text-white/50" />
            </button>

            {isExportMenuOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setIsExportMenuOpen(false)}
                />
                <div className="absolute top-full left-0 mt-2 w-56 bg-[#1f1f1f] border border-white/10 rounded-xl shadow-2xl py-1.5 z-50 animate-fadeIn">
                  {onExportSlide && (
                    <button
                      onClick={() => {
                        setIsExportMenuOpen(false);
                        onExportSlide();
                      }}
                      className="w-full text-left px-4 py-2 text-xs font-semibold text-white/90 hover:text-[#00ffcc] hover:bg-white/5 flex items-center gap-2 transition-colors"
                    >
                      <Download size={14} className="text-[#00ffcc]" />
                      <div>
                        <div>Export Current Slide</div>
                        <div className="text-[10px] text-white/40">Includes local fonts & images</div>
                      </div>
                    </button>
                  )}

                  {onExportPackage && (
                    <button
                      onClick={() => {
                        setIsExportMenuOpen(false);
                        onExportPackage();
                      }}
                      className="w-full text-left px-4 py-2 text-xs font-semibold text-white/90 hover:text-accentYellow hover:bg-white/5 flex items-center gap-2 transition-colors border-t border-white/5"
                    >
                      <Download size={14} className="text-accentYellow" />
                      <div>
                        <div>Export Station Package</div>
                        <div className="text-[10px] text-white/40">All slides & all assets</div>
                      </div>
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        <button 
          onClick={onSave}
          className="flex items-center gap-2 bg-statusGreen/20 hover:bg-statusGreen/30 text-statusGreen border border-statusGreen/40 px-4 py-1.5 rounded-full text-sm font-bold transition-all hover:scale-105 active:scale-95 whitespace-nowrap"
        >
          <Save size={16} />
          Save Overlay
        </button>
      </div>

      <div className="flex items-center gap-4 flex-shrink-0">
        <span className="text-xs text-textDim font-medium animate-pulse">{status}</span>
      </div>
    </div>
  );
}

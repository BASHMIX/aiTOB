import { useState, useRef } from 'react';
import { Upload, Download, Sparkles, LayoutTemplate, Layers, Check, Search } from 'lucide-react';
import { STARTER_OVERLAY_TEMPLATES, type EditorStarterTemplate } from '../starterTemplates';

interface LoadOverlayModalProps {
  isOpen: boolean;
  onClose: () => void;
  stationId: string;
  allSavedOverlays: { name: string; config: any }[];
  onLoad: (name: string) => void;
  onImportFile: (file: File) => void;
  onExportCurrentStationPackage?: () => void;
  onExportSingleSlide?: (name: string, config: any) => void;
  onLoadStarterTemplate?: (template: EditorStarterTemplate) => void;
}

export function LoadOverlayModal({
  isOpen,
  onClose,
  stationId,
  allSavedOverlays,
  onLoad,
  onImportFile,
  onExportCurrentStationPackage,
  onExportSingleSlide,
  onLoadStarterTemplate,
}: LoadOverlayModalProps) {
  const [activeTab, setActiveTab] = useState<'saved' | 'gallery'>('saved');
  const [galleryFilter, setGalleryFilter] = useState<'All' | 'Match' | 'Bracket' | 'Schedule' | 'Results'>('All');
  const [searchQuery, setSearchQuery] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onImportFile(file);
      e.target.value = '';
    }
  };

  const filteredSaved = allSavedOverlays.filter((o) =>
    o.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredTemplates = STARTER_OVERLAY_TEMPLATES.filter((t) => {
    const matchesCategory = galleryFilter === 'All' || t.category === galleryFilter;
    const matchesSearch = t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center z-[99999] p-6 animate-fadeIn">
      <div className="bg-[#1f1f1f] border border-white/10 rounded-2xl p-6 md:p-8 max-w-6xl w-full max-h-[90vh] flex flex-col relative shadow-2xl">
        {/* Hidden File Input for Import */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".json,.aitob-overlay.json,.aitob-package.json"
          className="hidden"
          onChange={handleFileChange}
        />

        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-6 right-6 w-9 h-9 rounded-full bg-white/5 border border-white/10 flex items-center justify-center hover:bg-red-500 hover:text-white transition-all text-sm font-bold text-white/70"
          title="Close modal"
        >
          ✕
        </button>

        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 pr-10">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-[#00ffcc] text-2xl font-black uppercase tracking-wider">
                Overlay Slide Manager
              </h2>
              <span className="bg-[#00ffcc]/10 text-[#00ffcc] text-[10px] font-bold px-2 py-0.5 rounded-full border border-[#00ffcc]/30 uppercase">
                Station: {stationId}
              </span>
            </div>
            <p className="text-[#aaa] text-xs mt-1">
              Switch between saved slides in this tournament or browse the curated starter templates gallery.
            </p>
          </div>

          {/* Quick Import / Package Export Action Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 bg-[#00ffcc]/15 hover:bg-[#00ffcc]/25 text-[#00ffcc] border border-[#00ffcc]/40 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all hover:scale-105 active:scale-95"
              title="Import overlay or package from a JSON file"
            >
              <Upload size={14} />
              Import File
            </button>

            {onExportCurrentStationPackage && (
              <button
                onClick={onExportCurrentStationPackage}
                className="flex items-center gap-1.5 bg-white/5 hover:bg-white/10 text-white border border-white/15 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all hover:scale-105 active:scale-95"
                title="Export all slides on this station as a single package"
              >
                <Download size={14} />
                Export Station Package
              </button>
            )}
          </div>
        </div>

        {/* Navigation Tabs and Search Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-b border-white/10 pb-4 mb-6">
          <div className="flex items-center gap-2 bg-[#141414] p-1 rounded-xl border border-white/5">
            <button
              onClick={() => setActiveTab('saved')}
              className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'saved'
                  ? 'bg-[#00ffcc] text-[#111] shadow-lg shadow-[#00ffcc]/20'
                  : 'text-white/60 hover:text-white hover:bg-white/5'
              }`}
            >
              <Layers size={14} />
              My Saved Slides ({allSavedOverlays.length})
            </button>

            <button
              onClick={() => setActiveTab('gallery')}
              className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'gallery'
                  ? 'bg-[#00ffcc] text-[#111] shadow-lg shadow-[#00ffcc]/20'
                  : 'text-white/60 hover:text-white hover:bg-white/5'
              }`}
            >
              <LayoutTemplate size={14} />
              <Sparkles size={13} className={activeTab === 'gallery' ? 'text-[#111]' : 'text-accentYellow'} />
              Template Gallery ({STARTER_OVERLAY_TEMPLATES.length})
            </button>
          </div>

          {/* Search box */}
          <div className="relative min-w-[240px]">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
            <input
              type="text"
              placeholder="Search slides or templates…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#141414] border border-white/10 rounded-xl pl-8 pr-3 py-1.5 text-xs text-white placeholder-white/40 focus:border-[#00ffcc] outline-none transition-colors"
            />
          </div>
        </div>

        {/* TAB 1: SAVED OVERLAYS */}
        {activeTab === 'saved' && (
          <div className="flex-grow overflow-y-auto pr-1">
            {filteredSaved.length === 0 ? (
              <div className="text-center py-20 text-white/40">
                <Layers size={40} className="mx-auto mb-3 opacity-30 text-[#00ffcc]" />
                <p className="text-base font-bold mb-1">
                  {searchQuery ? 'No slides matching your search' : 'No saved overlay slides found in DB'}
                </p>
                <p className="text-xs text-white/50 max-w-md mx-auto">
                  You can design and save slides in the editor, pick a ready-made slide from the{' '}
                  <span
                    onClick={() => setActiveTab('gallery')}
                    className="text-[#00ffcc] cursor-pointer hover:underline"
                  >
                    Template Gallery
                  </span>
                  , or import an existing slide file.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {filteredSaved.map((o) => {
                  const elCount = Object.keys(o.config?.elements || o.config?.nodes || {}).length;
                  return (
                    <div
                      key={o.name}
                      className="border border-white/10 rounded-xl p-4 bg-[#262626] hover:border-[#00ffcc] hover:bg-[#2c2c2c] transition-all flex flex-col group relative shadow-md overflow-hidden"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <span className="bg-[#00ffcc]/10 text-[#00ffcc] border border-[#00ffcc]/20 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide">
                          {elCount} Elements
                        </span>

                        {onExportSingleSlide && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onExportSingleSlide(o.name, o.config);
                            }}
                            className="text-white/40 hover:text-[#00ffcc] p-1 rounded hover:bg-white/5 transition-colors"
                            title={`Export '${o.name}' as file`}
                          >
                            <Download size={14} />
                          </button>
                        )}
                      </div>

                      {/* Preview Box */}
                      <div
                        onClick={() => onLoad(o.name)}
                        className="w-full h-28 bg-[#141414] rounded-lg border border-white/5 mb-3 relative flex flex-col items-center justify-center overflow-hidden cursor-pointer"
                      >
                        {o.config?.background_url || o.config?.canvas?.backgroundUrl ? (
                          <div
                            className="absolute inset-0 bg-cover bg-center opacity-40 group-hover:opacity-50 transition-opacity"
                            style={{
                              backgroundImage: `url('${o.config?.background_url || o.config?.canvas?.backgroundUrl}')`,
                            }}
                          />
                        ) : (
                          <div className="absolute inset-0 bg-checkerboard opacity-25" />
                        )}
                        <span className="text-white/90 text-xs font-bold z-10 group-hover:scale-105 transition-transform px-2 text-center">
                          {o.name}
                        </span>
                      </div>

                      <h3 className="font-bold text-sm text-white group-hover:text-[#00ffcc] transition-colors truncate">
                        {o.name}
                      </h3>
                      <p className="text-[11px] text-[#888] mt-0.5 truncate">
                        Font: {o.config?.global_font_family || o.config?.canvas?.globalFontFamily || 'System Default'}
                      </p>

                      <button
                        onClick={() => onLoad(o.name)}
                        className="w-full mt-3 py-1.5 bg-[#00ffcc] text-[#111] font-bold rounded-lg text-xs uppercase tracking-wider hover:bg-[#00d4aa] transition-colors flex items-center justify-center gap-1.5 shadow"
                      >
                        <Check size={14} />
                        Load Slide
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: STARTER TEMPLATES GALLERY */}
        {activeTab === 'gallery' && (
          <div className="flex-grow overflow-y-auto pr-1 flex flex-col">
            {/* Category Filter Pills */}
            <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-1">
              {(['All', 'Match', 'Bracket', 'Schedule', 'Results'] as const).map((cat) => (
                <button
                  key={cat}
                  onClick={() => setGalleryFilter(cat)}
                  className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition-all ${
                    galleryFilter === cat
                      ? 'bg-accentYellow text-black font-bold shadow'
                      : 'bg-white/5 text-white/70 hover:bg-white/10 hover:text-white border border-white/5'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            {filteredTemplates.length === 0 ? (
              <div className="text-center py-20 text-white/40">
                <p className="text-base font-bold mb-1">No templates found</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {filteredTemplates.map((template) => (
                  <div
                    key={template.id}
                    className="border border-white/10 rounded-xl p-5 bg-[#262626] hover:border-accentYellow/70 hover:bg-[#2c2c2c] transition-all flex flex-col group relative shadow-md"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="bg-accentYellow/15 text-accentYellow border border-accentYellow/30 rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider">
                        {template.badge}
                      </span>
                      <span className="text-[10px] text-white/40 font-mono">1920x1080</span>
                    </div>

                    <h3 className="font-bold text-base text-white group-hover:text-accentYellow transition-colors">
                      {template.name}
                    </h3>
                    <p className="text-xs text-[#aaa] mt-1 mb-4 flex-grow line-clamp-2">
                      {template.description}
                    </p>

                    <button
                      onClick={() => onLoadStarterTemplate?.(template)}
                      className="w-full py-2 bg-gradient-to-r from-accentYellow to-[#eab308] text-black font-bold rounded-lg text-xs uppercase tracking-wider hover:brightness-110 transition-all flex items-center justify-center gap-2 shadow"
                    >
                      <Sparkles size={14} />
                      Use This Template
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

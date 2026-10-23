import { useState } from 'react';
import { Image as ImageIcon, Type, Plus, X, ChevronUp, Sparkles } from 'lucide-react';
import { useEditorStore } from '@/store/useEditorStore';

const POPULAR_FONTS = [
  { name: 'Cairo', family: "'Cairo', sans-serif", url: 'https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap' },
  { name: 'Teko', family: "'Teko', sans-serif", url: 'https://fonts.googleapis.com/css2?family=Teko:wght@500;700&display=swap' },
  { name: 'Oswald', family: "'Oswald', sans-serif", url: 'https://fonts.googleapis.com/css2?family=Oswald:wght@500;700&display=swap' },
  { name: 'Bebas Neue', family: "'Bebas Neue', sans-serif", url: 'https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap' },
  { name: 'Inter', family: "'Inter', sans-serif", url: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap' },
  { name: 'Chakra Petch', family: "'Chakra Petch', sans-serif", url: 'https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;700&display=swap' },
];

export function SidebarGlobalSettings() {
  const store = useEditorStore();
  const [isAddFontOpen, setIsAddFontOpen] = useState(false);
  const [fontFamilyInput, setFontFamilyInput] = useState('');
  const [fontUrlInput, setFontUrlInput] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Auto-detect font family name when pasting a Google Font URL or <link>
  const handleUrlChange = (value: string) => {
    let cleanUrl = value.trim();
    const linkMatch = cleanUrl.match(/href=["'](https:\/\/fonts\.googleapis\.com[^"']+)["']/i);
    if (linkMatch) {
      cleanUrl = linkMatch[1];
    }
    setFontUrlInput(cleanUrl);

    if (!fontFamilyInput.trim()) {
      const familyMatch = cleanUrl.match(/[?&]family=([^:&]+)/i);
      if (familyMatch) {
        const detectedName = decodeURIComponent(familyMatch[1]).replace(/\+/g, ' ');
        setFontFamilyInput(`'${detectedName}', sans-serif`);
      }
    }
  };

  const handleAddCustomFont = () => {
    setErrorMsg('');
    const rawFamily = fontFamilyInput.trim();
    if (!rawFamily) {
      setErrorMsg('Please enter a font family name.');
      return;
    }

    // Format font family if simple word without quotes/generic fallback
    const family = rawFamily.includes(',') || rawFamily.startsWith("'") || rawFamily.startsWith('"')
      ? rawFamily
      : `'${rawFamily}', sans-serif`;

    const url = fontUrlInput.trim();

    store.setFontLibrary([{ family, url: url || undefined }]);
    store.setGlobalSettings(store.background_url, url || store.global_font_url, family);

    setFontFamilyInput('');
    setFontUrlInput('');
    setIsAddFontOpen(false);
  };

  const handleAddPreset = (preset: typeof POPULAR_FONTS[0]) => {
    store.setFontLibrary([{ family: preset.family, url: preset.url }]);
    store.setGlobalSettings(store.background_url, preset.url, preset.family);
  };

  return (
    <div className="flex flex-col gap-3">
      {/* Background Image Setting */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-[11px] text-[#999] uppercase tracking-wide flex items-center gap-1.5 font-bold">
            <ImageIcon size={13} className="text-[#00ffcc]" />
            Background Image
          </label>
          {store.background_url && (
            <button
              type="button"
              onClick={() => store.setGlobalSettings('', store.global_font_url, store.global_font_family)}
              className="text-[10px] text-red-400 hover:text-red-300 transition-colors"
              title="Remove background image"
            >
              Clear
            </button>
          )}
        </div>
        <div className="relative">
          <input
            type="text"
            className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2.5 py-1.5 text-xs text-white placeholder-white/30 focus:border-[#00ffcc] outline-none pr-7 transition-colors"
            placeholder="Image URL (/static/... or https://...)"
            value={store.background_url}
            onChange={(e) => store.setGlobalSettings(e.target.value, store.global_font_url, store.global_font_family)}
          />
          {store.background_url && (
            <button
              type="button"
              onClick={() => store.setGlobalSettings('', store.global_font_url, store.global_font_family)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-white/40 hover:text-white"
            >
              <X size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Canvas Global Typography */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-[11px] text-[#999] uppercase tracking-wide flex items-center gap-1.5 font-bold">
            <Type size={13} className="text-[#00ffcc]" />
            Canvas Font
          </label>
          <button
            type="button"
            onClick={() => { setIsAddFontOpen(!isAddFontOpen); setErrorMsg(''); }}
            className="text-[10px] font-bold text-[#00ffcc] hover:text-white flex items-center gap-1 transition-colors"
          >
            {isAddFontOpen ? <ChevronUp size={12} /> : <Plus size={12} />}
            {isAddFontOpen ? 'Close' : 'Add Font'}
          </button>
        </div>

        {/* Global Font Selector Dropdown */}
        <select
          className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 text-xs text-white focus:border-[#00ffcc] outline-none mb-2 transition-colors"
          value={store.global_font_family || ''}
          onChange={(e) => {
            const family = e.target.value;
            const selected = store.font_library.find((font) => font.family === family);
            store.setGlobalSettings(store.background_url, selected?.url || (family ? store.global_font_url : ''), family);
          }}
          title="Choose active global font"
        >
          <option className="bg-[#222] text-white" value="">System Default</option>
          {store.font_library.map((font) => (
            <option className="bg-[#222] text-white" key={font.family} value={font.family}>
              {font.family.replace(/['",]/g, '').replace('sans-serif', '').trim()}
            </option>
          ))}
          {store.global_font_family && !store.font_library.some((f) => f.family === store.global_font_family) && (
            <option className="bg-[#222] text-white" value={store.global_font_family}>
              {store.global_font_family}
            </option>
          )}
        </select>

        {/* Live Font Sample Preview */}
        {store.global_font_family && (
          <div
            className="mb-2 px-2.5 py-1.5 rounded bg-[#1e1e1e] border border-white/10 text-center text-xs truncate text-[#00ffcc]"
            style={{ fontFamily: store.global_font_family }}
            title={`Previewing ${store.global_font_family}`}
          >
            Aa Bb 123 • FINAL MATCH
          </div>
        )}

        {/* Saved Font Chips */}
        <div className="flex flex-wrap gap-1.5 mb-2">
          <button
            type="button"
            onClick={() => store.setGlobalSettings(store.background_url, '', '')}
            className={`px-2 py-0.5 rounded text-[10px] border transition-colors ${
              !store.global_font_family
                ? 'bg-[#00ffcc]/20 border-[#00ffcc] text-[#00ffcc] font-bold'
                : 'bg-[#222] border-[#444] text-white/70 hover:text-white'
            }`}
          >
            Default
          </button>
          {store.font_library.map((font) => {
            const isActive = store.global_font_family === font.family;
            const cleanName = font.family.replace(/['",]/g, '').replace('sans-serif', '').trim();
            return (
              <span
                key={font.family}
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] border transition-colors ${
                  isActive
                    ? 'bg-[#00ffcc]/20 border-[#00ffcc] text-[#00ffcc] font-bold'
                    : 'bg-[#222] border-[#444] text-white/70 hover:text-white'
                }`}
              >
                <button
                  type="button"
                  onClick={() => store.setGlobalSettings(store.background_url, font.url || store.global_font_url, font.family)}
                  className="hover:underline truncate max-w-[100px]"
                  title={`Apply ${cleanName}`}
                >
                  {cleanName}
                </button>
                <button
                  type="button"
                  onClick={() => store.removeFontFromLibrary(font.family)}
                  className="text-white/40 hover:text-red-400 ml-0.5"
                  title={`Remove ${cleanName}`}
                >
                  <X size={10} />
                </button>
              </span>
            );
          })}
        </div>

        {/* Collapsible Add Font Form */}
        {isAddFontOpen && (
          <div className="bg-[#1f1f1f] border border-[#444] rounded p-2.5 mt-2 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-white/70 flex items-center gap-1">
                <Sparkles size={11} className="text-[#00ffcc]" />
                Add Google or Custom Font
              </span>
            </div>

            {/* Quick Popular Esports / Stream Presets */}
            <div>
              <div className="text-[9px] text-[#888] uppercase mb-1">Quick Presets:</div>
              <div className="flex flex-wrap gap-1">
                {POPULAR_FONTS.map((preset) => {
                  const isAdded = store.font_library.some((f) => f.family === preset.family);
                  return (
                    <button
                      key={preset.name}
                      type="button"
                      onClick={() => handleAddPreset(preset)}
                      className={`px-1.5 py-0.5 rounded text-[10px] border transition-all ${
                        isAdded
                          ? 'border-[#00ffcc]/40 bg-[#00ffcc]/10 text-[#00ffcc]'
                          : 'border-white/10 bg-[#2a2a2a] text-white/80 hover:bg-[#333] hover:text-white'
                      }`}
                      title={isAdded ? 'Already added' : `Add ${preset.name}`}
                    >
                      {preset.name} {isAdded && '✓'}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Manual Entry */}
            <div className="flex flex-col gap-1.5 pt-1 border-t border-white/5">
              <input
                type="text"
                className="bg-[#2a2a2a] border border-[#555] rounded px-2 py-1 text-xs text-white placeholder-white/30 focus:border-[#00ffcc] outline-none"
                placeholder="Google Font URL (or <link> tag)"
                value={fontUrlInput}
                onChange={(e) => handleUrlChange(e.target.value)}
              />

              <input
                type="text"
                className="bg-[#2a2a2a] border border-[#555] rounded px-2 py-1 text-xs text-white placeholder-white/30 focus:border-[#00ffcc] outline-none"
                placeholder="Font Family (e.g. Montserrat or Arial)"
                value={fontFamilyInput}
                onChange={(e) => setFontFamilyInput(e.target.value)}
              />

              {errorMsg && (
                <div className="text-[10px] text-red-400">{errorMsg}</div>
              )}

              <div className="flex gap-2 mt-1">
                <button
                  type="button"
                  onClick={handleAddCustomFont}
                  className="flex-1 bg-[#00ffcc] hover:bg-[#00d4aa] text-[#111] font-bold py-1 px-2 rounded text-xs transition-colors"
                >
                  Save & Apply Font
                </button>
                <button
                  type="button"
                  onClick={() => setIsAddFontOpen(false)}
                  className="bg-[#333] hover:bg-[#444] text-white/70 py-1 px-2 rounded text-xs transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

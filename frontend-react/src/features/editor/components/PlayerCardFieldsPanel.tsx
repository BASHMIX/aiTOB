import { useEditorStore, type OverlayElement } from '@/store/useEditorStore';
import { findResultCardDefinitionContext } from '../resultsTemplateContext';
import { FLAG_IMAGE_PLACEHOLDER, PLAYER_IMAGE_PLACEHOLDER } from '@/utils/overlayAssets';

type FieldDefinition = {
  binding: string;
  label: string;
  icon: string;
  create: (id: string, parentId: string) => OverlayElement;
};

const FIELD_DEFINITIONS: FieldDefinition[] = [
  {
    binding: 'placement', label: 'Placement', icon: '🏆',
    create: (id, parentId) => ({
      id, parentId, name: 'Placement', type: 'text', binding: 'placement', text: '1',
      visible: true, x: 18, y: 18, width: 72, height: 58, fontSize: 30,
      fontWeight: 'bold', textAlign: 'center', color: '#ffffff', zIndex: 6,
    }),
  },
  {
    binding: 'displayName', label: 'Player Name', icon: '🔤',
    create: (id, parentId) => ({
      id, parentId, name: 'Player Name', type: 'text', binding: 'displayName', text: 'Player',
      visible: true, x: 106, y: 42, width: 286, height: 38, fontSize: 28,
      fontWeight: 'bold', textAlign: 'left', color: '#ffffff', zIndex: 6,
    }),
  },
  {
    binding: 'prefix', label: 'Prefix / Team', icon: '🏷️',
    create: (id, parentId) => ({
      id, parentId, name: 'Team / Prefix', type: 'text', binding: 'prefix', text: 'TEAM',
      visible: true, x: 106, y: 18, width: 240, height: 24, fontSize: 16,
      fontWeight: 'bold', textAlign: 'left', color: '#9ca3af', zIndex: 5,
    }),
  },
  {
    binding: 'avatarUrl', label: 'Player Photo', icon: '👤',
    create: (id, parentId) => ({
      id, parentId, name: 'Player Photo', type: 'image', binding: 'avatarUrl',
      src: PLAYER_IMAGE_PLACEHOLDER, visible: true, x: 24, y: 352, width: 126, height: 126,
      borderRadius: 14, zIndex: 5,
    }),
  },
  {
    binding: 'countryFlagUrl', label: 'Country Flag', icon: '🏳️',
    create: (id, parentId) => ({
      id, parentId, name: 'Country Flag', type: 'image', binding: 'countryFlagUrl',
      src: FLAG_IMAGE_PLACEHOLDER, visible: true, x: 164, y: 366, width: 74, height: 50,
      borderRadius: 4, zIndex: 5,
    }),
  },
  {
    binding: 'countryCode', label: 'Country Code', icon: '🌐',
    create: (id, parentId) => ({
      id, parentId, name: 'Country Code', type: 'text', binding: 'countryCode', text: 'JO',
      visible: true, x: 246, y: 376, width: 70, height: 22, fontSize: 16,
      fontWeight: 'bold', textAlign: 'center', color: '#d1d5db', zIndex: 5,
    }),
  },
  {
    binding: 'characterName', label: 'Character Name', icon: '🎮',
    create: (id, parentId) => ({
      id, parentId, name: 'Character Name', type: 'text', binding: 'characterName', text: 'Character',
      visible: true, x: 164, y: 424, width: 228, height: 32, fontSize: 19,
      fontWeight: 'bold', textAlign: 'left', color: '#ffffff', zIndex: 5,
    }),
  },
  {
    binding: 'characterImageUrl', label: 'Character Art', icon: '🕹️',
    create: (id, parentId) => ({
      id, parentId, name: 'Character Art', type: 'image', binding: 'characterImageUrl',
      src: PLAYER_IMAGE_PLACEHOLDER, visible: true, x: 18, y: 86, width: 384, height: 260,
      borderRadius: 12, zIndex: 2,
    }),
  },
];

export function PlayerCardFieldsPanel() {
  const store = useEditorStore();
  const context = findResultCardDefinitionContext(store.elements, store.editingResultCardDefinitionId);
  if (!context || context.definition.type !== 'group') return null;

  const childIds = context.definition.childIds || [];
  const existingBindings = new Set(
    childIds.map((id) => store.elements[id]?.binding).filter(Boolean),
  );

  const addField = (definition: FieldDefinition) => {
    if (existingBindings.has(definition.binding)) return;
    const baseId = `${context.definition.id}_${definition.binding}`;
    let id = baseId;
    let suffix = 2;
    while (store.elements[id]) id = `${baseId}_${suffix++}`;
    const field = definition.create(id, context.definition.id);

    store.takeSnapshot();
    store.setElements({
      ...store.elements,
      [id]: field,
      [context.definition.id]: {
        ...context.definition,
        childIds: [...childIds, id],
      },
    });
    store.setSelectedId(id);
  };

  const addPrimitive = (type: 'text' | 'image' | 'rect') => {
    const id = `${context.definition.id}_${type}_${Date.now()}`;
    const base = { id, parentId: context.definition.id, name: `Custom ${type}`, visible: true, x: 40, y: 120, width: 180, height: 70, zIndex: 10 };
    const field: OverlayElement = type === 'text'
      ? { ...base, type, text: 'Custom Text', fontSize: 24, color: '#ffffff' }
      : type === 'image'
        ? { ...base, type, src: PLAYER_IMAGE_PLACEHOLDER, height: 180 }
        : { ...base, type, color: 'rgba(14,165,233,0.35)', borderRadius: 12 };
    store.takeSnapshot();
    store.setElements({
      ...store.elements,
      [id]: field,
      [context.definition.id]: { ...context.definition, childIds: [...childIds, id] },
    });
    store.setSelectedId(id);
  };

  return (
    <div className="mb-4 mt-10 rounded-lg border border-[#00ffcc]/20 bg-[#00ffcc]/5 p-3">
      <h2 className="text-xs font-bold uppercase tracking-wider text-[#00ffcc]">Player Card Fields</h2>
      <p className="mb-3 mt-1 text-[10px] leading-relaxed text-white/55">
        Add a bound field once, then position and style it like any other layer. Tournament data replaces the preview automatically.
      </p>
      <div className="grid grid-cols-2 gap-2">
        {FIELD_DEFINITIONS.map((definition) => {
          const exists = existingBindings.has(definition.binding);
          return (
            <button
              key={definition.binding}
              type="button"
              disabled={exists}
              onClick={() => addField(definition)}
              className={`rounded border px-2 py-2 text-left text-[11px] font-semibold transition-colors ${
                exists
                  ? 'cursor-default border-white/5 bg-white/5 text-white/30'
                  : 'border-[#00ffcc]/20 bg-[#242d31] text-white hover:border-[#00ffcc]/60 hover:bg-[#00ffcc]/10'
              }`}
            >
              <span className="mr-1.5">{definition.icon}</span>{definition.label}
              {exists && <span className="ml-1 text-[9px] uppercase text-[#00ffcc]/55">Added</span>}
            </button>
          );
        })}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 border-t border-white/10 pt-3">
        <button type="button" onClick={() => addPrimitive('text')} className="rounded border border-white/10 bg-white/5 px-2 py-1.5 text-[10px] font-bold hover:bg-white/10">+ Text</button>
        <button type="button" onClick={() => addPrimitive('image')} className="rounded border border-white/10 bg-white/5 px-2 py-1.5 text-[10px] font-bold hover:bg-white/10">+ Image</button>
        <button type="button" onClick={() => addPrimitive('rect')} className="rounded border border-white/10 bg-white/5 px-2 py-1.5 text-[10px] font-bold hover:bg-white/10">+ Shape</button>
      </div>
    </div>
  );
}

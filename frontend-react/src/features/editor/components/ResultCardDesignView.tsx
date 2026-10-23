import { Rnd } from 'react-rnd';
import { useEditorStore } from '@/store/useEditorStore';
import { CardTemplateNode } from '@/scene/CardTemplateNode';
import { MOCK_DATASETS } from '@/features/results/mockData';
import { findResultCardDefinitionContext } from '../resultsTemplateContext';
import type { GroupNode, SceneDocumentV2 } from '@/scene/types';

export function ResultCardDesignView({ scale = 1 }: { scale?: number }) {
  const store = useEditorStore();
  const context = findResultCardDefinitionContext(store.elements, store.editingResultCardDefinitionId);
  if (!context || context.definition.type !== 'group') return null;

  const definition = context.definition as GroupNode;
  const datasetKey = context.resultsGroup?.preview?.dataset
    || (context.resultCard?.parentId ? store.elements[context.resultCard.parentId]?.preview?.dataset : undefined)
    || 'normal';
  const standing = (MOCK_DATASETS[datasetKey] || MOCK_DATASETS.normal)[0];
  if (!standing) return null;

  const width = definition.width || 420;
  const height = definition.height || 560;
  const scene: SceneDocumentV2 = {
    schemaVersion: 2,
    canvas: { width, height },
    dataSource: { kind: 'tournament-results' },
    rootIds: [],
    nodes: store.elements as any,
  };

  const children = definition.childIds
    .map((id) => store.elements[id])
    .filter(Boolean)
    .sort((a, b) => (a.zIndex || 0) - (b.zIndex || 0));

  return (
    <div
      data-testid="result-card-design-view"
      data-overlay-element="true"
      className="absolute inset-0 z-[500] bg-[#0d131c]"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) store.setSelectedId(definition.id);
      }}
    >
      <div className="absolute left-10 right-10 top-7 flex items-start justify-between border-b border-[#00ffcc]/20 pb-4 text-left">
        <div>
          <div className="text-sm font-black uppercase tracking-[0.22em] text-[#00ffcc]">Result Card · Design</div>
          <div className="mt-1 text-xs text-white/45">Edit the shared card layers. Changes update freeform cards, Results Groups, exports, and OBS.</div>
        </div>
        <div className="flex items-center gap-3">
          <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-white/55">Mock Player · #{standing.placement}</div>
          <button
            type="button"
            onClick={() => {
              store.exitResultCardDesign();
              if (context.owner) store.setSelectedId(context.owner.id);
            }}
            className="rounded-lg border border-[#00ffcc]/30 bg-[#00ffcc]/10 px-4 py-2 text-xs font-black text-[#00ffcc] hover:bg-[#00ffcc]/20"
          >
            Done Editing Card
          </button>
        </div>
      </div>

      <div
        className="absolute rounded-xl shadow-[0_30px_90px_rgba(0,0,0,0.55)] ring-2 ring-[#00ffcc]/35"
        style={{ left: (1920 - width) / 2, top: Math.max(140, (1080 - height) / 2 + 24), width, height }}
        onMouseDown={(event) => {
          if (event.target === event.currentTarget) store.setSelectedId(definition.id);
        }}
      >
        {children.map((child) => {
          const selected = store.selectedId === child.id || store.selectedIds.includes(child.id);
          return (
            <Rnd
              key={child.id}
              scale={scale}
              bounds="parent"
              position={{ x: child.x || 0, y: child.y || 0 }}
              size={{ width: child.width || 100, height: child.height || 50 }}
              disableDragging={child.locked === true}
              enableResizing={child.locked !== true}
              onDragStart={() => {
                store.takeSnapshot();
                store.setSelectedId(child.id);
              }}
              onDrag={(_event, data) => store.updateElement(child.id, { x: Math.round(data.x), y: Math.round(data.y) })}
              onResizeStart={() => {
                store.takeSnapshot();
                store.setSelectedId(child.id);
              }}
              onResize={(_event, _direction, ref, _delta, position) => store.updateElement(child.id, {
                x: Math.round(position.x),
                y: Math.round(position.y),
                width: Math.round(ref.offsetWidth),
                height: Math.round(ref.offsetHeight),
              })}
              style={{ zIndex: selected ? 1000 : (child.zIndex || 1) }}
              data-overlay-element="true"
              data-overlay-element-id={child.id}
              data-testid={selected ? 'result-card-selected-child' : `result-card-child-${child.id}`}
              data-selected={selected ? 'true' : 'false'}
              className={selected ? 'outline outline-2 outline-dashed outline-[#00ffcc]' : ''}
              onMouseDown={(event) => {
                event.stopPropagation();
                store.setSelectedId(child.id);
              }}
            >
              <CardTemplateNode
                scene={scene}
                nodeId={child.id}
                standing={standing}
                scaleX={1}
                scaleY={1}
                variantOverrides={{}}
                cueVisible
                fillParent
              />
            </Rnd>
          );
        })}
      </div>
    </div>
  );
}

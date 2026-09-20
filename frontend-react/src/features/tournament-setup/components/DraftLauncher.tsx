import type { SetupDraft } from '../types';

export function DraftLauncher({ drafts, onSelect }: { drafts: SetupDraft[]; onSelect: (draft: SetupDraft) => void }) {
  return <section aria-label="Saved tournament drafts" className="space-y-3"><h2 className="text-lg font-semibold">Resume setup</h2>{drafts.length === 0 ? <p className="text-sm text-textDim">No saved drafts.</p> : drafts.map((draft) => <button key={draft.id} type="button" onClick={() => onSelect(draft)} className="flex min-h-11 w-full items-center justify-between rounded-lg border border-white/10 px-4 py-3 text-left hover:border-white/25"><span><span className="block text-sm font-medium">{String(draft.tournament_review.display_name || 'Untitled tournament')}</span><span className="text-xs text-textDim">Step: {draft.current_step} · Revision {draft.revision}</span></span><span className="text-xs text-textDim">{draft.status}</span></button>)}</section>;
}

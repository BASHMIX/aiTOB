import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useHubStore } from '@/store/useHubStore';
import { useHubSocket } from '@/hooks/useHubSocket';
import { ActionProposalReview } from './ActionProposalReview';

type Tab = 'attention' | 'dispatch' | 'approvals' | 'timeline' | 'assistant';
type ConsoleData = any;
const tabs: Array<[Tab, string]> = [['attention', 'Attention'], ['dispatch', 'Dispatch'], ['approvals', 'Approvals'], ['timeline', 'Timeline'], ['assistant', 'Assistant']];

function Empty({ children }: { children: React.ReactNode }) { return <p className="py-8 text-center text-xs italic text-textDim">{children}</p>; }
function Item({ children }: { children: React.ReactNode }) { return <article className="rounded-lg border border-white/10 bg-black/20 p-2.5 text-xs text-gray-200">{children}</article>; }

export function OrganizerConsole() {
  const { currentSlug, tournaments } = useHubStore();
  const tournament = tournaments.find((item) => item.slug === currentSlug);
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>('attention');
  const [data, setData] = useState<ConsoleData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const requestSequence = useRef(0);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [asking, setAsking] = useState(false);
  const [messages, setMessages] = useState<Array<{ sender: 'user' | 'assistant'; text: string; at: string }>>([]);

  const refresh = useCallback(async () => {
    if (!currentSlug) { setData(null); return; }
    const sequence = ++requestSequence.current;
    setLoading(true); setError(null);
    try {
      const response = await axios.get(`/api/organizer-console/${currentSlug}`);
      if (sequence === requestSequence.current) setData(response.data);
    } catch (requestError) {
      if (sequence === requestSequence.current) setError(axios.isAxiosError(requestError) ? (requestError.response?.data?.message || 'Could not load local console data.') : 'Could not load local console data.');
    } finally { if (sequence === requestSequence.current) setLoading(false); }
  }, [currentSlug]);

  useEffect(() => { if (open) void refresh(); }, [open, refresh]);
  useEffect(() => {
    setData(null); setError(null); setAnswer('');
    setMessages(currentSlug ? JSON.parse(localStorage.getItem(`organizer_assistant_chat_v3:${currentSlug}`) || '[]') : []);
  }, [currentSlug]);
  useEffect(() => {
    if (currentSlug) localStorage.setItem(`organizer_assistant_chat_v3:${currentSlug}`, JSON.stringify(messages));
  }, [currentSlug, messages]);
  useHubSocket(useCallback((event) => {
    if (open && ['match_update', 'status_update'].includes(event.type)) void refresh();
  }, [open, refresh]));

  const ask = async () => {
    const text = question.trim(); if (!text || !currentSlug) return;
    setAsking(true); setAnswer(''); setMessages((current) => [...current, { sender: 'user', text, at: new Date().toISOString() }]);
    try {
      const response = await axios.post(`/api/ai/assistant/${encodeURIComponent(currentSlug)}`, { question: text });
      const reply = String(response.data?.answer || 'No response received.');
      setMessages((current) => [...current, { sender: 'assistant', text: reply, at: new Date().toISOString() }]);
      setAnswer(response.data?.proposal ? 'A proposal was created for organizer review; it has not executed.' : 'Read-only answer received.'); setQuestion('');
    } catch (requestError: any) { setAnswer(requestError?.response?.data?.message || 'Could not reach the Assistant service. Operational data above remains local.'); }
    finally { setAsking(false); }
  };

  if (!open) return <button onClick={() => setOpen(true)} className="fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-full border border-white/10 bg-[#161a21] px-4 py-2.5 text-xs font-bold tracking-wide text-gray-200 shadow-2xl hover:border-accentYellow/40"><span className="h-2 w-2 rounded-full bg-accentYellow" />AI Organizer Console</button>;
  return <aside className="fixed bottom-4 right-4 z-50 flex h-[620px] w-[420px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-xl border border-white/10 bg-cardDark shadow-2xl">
    <header className="border-b border-white/10 bg-[#13171f] p-3">
      <div className="flex items-center justify-between gap-2"><div><h2 className="text-xs font-bold uppercase tracking-widest text-accentYellow">AI Organizer Console</h2><p className="mt-1 text-[10px] text-textDim">{tournament ? `${tournament.name} · ${tournament.provider_type === 'challonge' ? 'Challonge' : 'Start.gg'}` : 'Select a tournament to inspect local operations.'}</p></div><button onClick={() => setOpen(false)} className="px-1 text-sm font-bold text-textDim hover:text-white">×</button></div>
      {currentSlug && <div className="mt-2 flex items-center justify-between text-[10px] text-textDim"><span>{data?.refreshed_at ? `Last updated ${new Date(data.refreshed_at).toLocaleTimeString()}` : loading ? 'Loading local state…' : 'Not loaded'}</span><button onClick={() => void refresh()} className="rounded border border-white/10 px-2 py-1 hover:text-white">Refresh</button></div>}
      <nav className="mt-3 flex gap-1 overflow-x-auto">{tabs.map(([id, label]) => <button key={id} onClick={() => setTab(id)} className={`rounded px-2 py-1 text-[10px] font-bold ${tab === id ? 'bg-accentYellow/15 text-accentYellow' : 'text-textDim hover:text-white'}`}>{label}</button>)}</nav>
    </header>
    <main className="min-h-0 flex-1 overflow-y-auto p-3 custom-scrollbar">
      {!currentSlug ? <Empty>Choose a tournament from the main tournament list first.</Empty> : error ? <Empty>Could not load local console data: {error}</Empty> : !data ? <Empty>{loading ? 'Loading SQLite projection…' : 'No local console data yet.'}</Empty> : <>
        {tab === 'attention' && <div className="space-y-2">{data.attention.provider_outage.active && <Item><b className="text-statusRed">Provider outage</b><p className="mt-1 text-textDim">{data.attention.provider_outage.message || 'Provider synchronization is unavailable. Local state remains readable.'}</p></Item>}{data.attention.conflicts.map((item: any) => <Item key={`conflict-${item.id}`}><b className="text-statusRed">Conflict</b> · {item.p1_name} vs {item.p2_name}</Item>)}{data.attention.failed_commands.map((item: any) => <Item key={item.id}><b className="text-statusRed">Provider command {item.state}</b> · {item.action} · {item.set_id}</Item>)}{data.attention.awaiting_verification.map((item: any) => <Item key={item.id}><b className="text-amber-200">Awaiting verification</b> · {item.action} · {item.set_id} · {item.state}</Item>)}{!data.attention.provider_outage.active && !data.attention.conflicts.length && !data.attention.failed_commands.length && !data.attention.awaiting_verification.length && <Empty>No attention items for this tournament.</Empty>}</div>}
        {tab === 'dispatch' && <div className="space-y-2"><Item><div className="flex justify-between"><b>Dispatcher</b><span className={data.dispatch.state === 'running' ? 'text-statusGreen' : 'text-amber-200'}>{data.dispatch.state}</span></div><p className="mt-1 text-textDim">Slots: {data.dispatch.slots_available} available / {data.dispatch.capacity}; {data.dispatch.active_slots} active. Configure policy in Match operations.</p></Item>{data.dispatch.decisions.map((item: any) => <Item key={item.id}><b>{item.decision === 'select' ? 'Selected' : 'Skipped'}</b> · {item.set_id || 'event'}<p className="mt-1 text-textDim">{item.reason_code}: {item.explanation}</p></Item>)}{!data.dispatch.decisions.length && <Empty>No Dispatcher decisions recorded yet.</Empty>}</div>}
        {tab === 'approvals' && <ActionProposalReview tournamentSlug={currentSlug} />}
        {tab === 'timeline' && <div className="space-y-2">{data.timeline.map((item: any) => <Item key={`${item.kind}-${item.id}`}><div className="flex justify-between gap-2"><b>{item.kind.replace('_', ' ')}</b><span className="font-mono text-textDim">{item.status}</span></div><p className="mt-1 text-textDim">{item.action || item.event_type || item.source || 'event'} · {item.match_id || 'tournament'} · {item.at ? new Date(item.at).toLocaleString() : '—'}</p></Item>)}{!data.timeline.length && <Empty>No linked local events for this tournament.</Empty>}</div>}
        {tab === 'assistant' && <div className="space-y-3"><Item><b>Read-only Assistant</b><p className="mt-1 text-textDim">Question scope: {tournament?.name || currentSlug}. It can explain local state but cannot approve, Call, announce, score, DQ, reopen, or control stations.</p></Item>{messages.map((message, index) => <div key={`${message.at}-${index}`} className={`rounded-lg p-2 text-xs ${message.sender === 'user' ? 'ml-8 bg-accentYellow/10 text-white' : 'mr-8 bg-black/25 text-gray-200'}`}><p>{message.text}</p><span className="mt-1 block text-[9px] text-textDim">{new Date(message.at).toLocaleTimeString()}</span></div>)}<textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about this tournament’s local state…" className="min-h-24 w-full rounded border border-white/10 bg-black/30 p-2 text-xs text-white" /><button disabled={asking || !question.trim()} onClick={ask} className="rounded bg-accentYellow px-3 py-2 text-xs font-bold text-black disabled:opacity-40">{asking ? 'Asking…' : 'Ask Assistant'}</button>{answer && <Item>{answer}</Item>}</div>}
      </>}
    </main>
  </aside>;
}

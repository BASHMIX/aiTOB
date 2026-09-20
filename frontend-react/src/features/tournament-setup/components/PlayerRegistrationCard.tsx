import { useState } from 'react';
import type { ProviderType, RegistrationConfig } from '../types';

interface PlayerRegistrationCardProps {
  value: Partial<RegistrationConfig>;
  providerType?: ProviderType;
  onChange: (value: RegistrationConfig) => void;
  disabled?: boolean;
}

export const DEFAULT_REGISTRATION_CONFIG: RegistrationConfig = {
  enabled: false,
  destination_external_id: '',
  opens_at: '',
  closes_at: '',
  display_timezone: 'UTC',
  require_provider_registration: true,
  gamertag_verification_policy: 'match_or_set_nickname',
  startgg_bio_verification_enabled: false,
  image_policy: 'optional',
  verified_role_external_id: '',
};

const inputClass = 'mt-1 w-full rounded-lg border border-white/10 bg-appDark px-3 py-2.5 text-sm text-white outline-none transition focus:border-accentYellow/60 [color-scheme:dark]';

function dateTimeParts(value: string | undefined) {
  const raw = String(value || '').trim();
  const match = raw.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
  if (match) return { date: match[1], time: match[2] };
  return { date: '', time: '' };
}

function dateTimeLabel(value: string | undefined) {
  const { date, time } = dateTimeParts(value);
  if (!date || !time) return 'Select date and time';
  const [year, month, day] = date.split('-').map(Number);
  const [hour, minute] = time.split(':').map(Number);
  const parsed = new Date(year, month - 1, day, hour, minute);
  return Number.isNaN(parsed.getTime())
    ? `${date} · ${time}`
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(parsed);
}

function DateTimePicker({
  id,
  label,
  value,
  onChange,
  disabled,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const parts = dateTimeParts(value);
  const inputValue = parts.date && parts.time ? `${parts.date}T${parts.time}` : '';
  const updatePart = (part: 'date' | 'time', nextValue: string) => {
    const next = { ...parts, [part]: nextValue };
    if (next.date) onChange(`${next.date}T${next.time || '00:00'}`);
  };

  return (
    <div className="relative">
      <label className="block text-xs font-medium text-textDim" htmlFor={id}>{label}
        <div className="relative">
          <input
            id={id}
            type="datetime-local"
            value={inputValue}
            onChange={(event) => onChange(event.target.value)}
            className={`${inputClass} pr-11`}
            disabled={disabled}
          />
          <button
            type="button"
            aria-label={`Choose ${label.toLowerCase()}`}
            aria-expanded={open}
            disabled={disabled}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              setOpen((current) => !current);
            }}
            className="absolute right-1 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-md text-accentYellow transition hover:bg-accentYellow/10 disabled:opacity-40"
          >
            <span aria-hidden="true">▣</span>
          </button>
        </div>
      </label>
      {open && !disabled && (
        <div role="dialog" aria-label={`${label} date picker`} className="absolute z-30 mt-2 w-full min-w-[17rem] rounded-xl border border-white/15 bg-cardDark p-3 shadow-2xl">
          <p className="mb-3 text-[10px] font-mono uppercase tracking-wider text-accentYellow">{label}</p>
          <div className="grid grid-cols-2 gap-3">
            <label className="text-[11px] text-textDim">Date
              <input type="date" value={parts.date} onChange={(event) => updatePart('date', event.target.value)} className={inputClass} />
            </label>
            <label className="text-[11px] text-textDim">Time
              <input type="time" value={parts.time} onChange={(event) => updatePart('time', event.target.value)} className={inputClass} />
            </label>
          </div>
          <p className="mt-3 text-xs text-textDim">{dateTimeLabel(value)}</p>
          <div className="mt-3 flex justify-between gap-2 border-t border-white/10 pt-3">
            <button type="button" onClick={() => { onChange(''); setOpen(false); }} className="rounded-md px-2 py-1.5 text-xs text-textDim hover:bg-white/5">Clear</button>
            <button type="button" onClick={() => setOpen(false)} className="rounded-md bg-accentYellow px-3 py-1.5 text-xs font-bold text-black">Done</button>
          </div>
        </div>
      )}
    </div>
  );
}

export function PlayerRegistrationCard({ value, providerType = 'startgg', onChange, disabled = false }: PlayerRegistrationCardProps) {
  const config: RegistrationConfig = { ...DEFAULT_REGISTRATION_CONFIG, ...value };
  const patch = (next: Partial<RegistrationConfig>) => onChange({ ...config, ...next });
  return (
    <section className="rounded-xl border border-white/10 bg-black/10 p-4 sm:p-5" data-testid="player-registration-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h3 className="text-base font-semibold text-white">Discord player registration</h3><p className="mt-1 max-w-2xl text-xs leading-relaxed text-textDim">Open a scheduled registration window, sync provider entrants, and let the bot collect confirmation and player images.</p></div>
        <label className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold text-white"><input type="checkbox" checked={config.enabled} disabled={disabled} onChange={(event) => patch({ enabled: event.target.checked })} /> Enable registration</label>
      </div>
      <fieldset disabled={disabled || !config.enabled} className="mt-5 space-y-5 disabled:opacity-60">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <DateTimePicker id="registration-opens" label="Opens at" value={config.opens_at} onChange={(opens_at) => patch({ opens_at })} disabled={disabled || !config.enabled} />
          <DateTimePicker id="registration-closes" label="Closes at" value={config.closes_at} onChange={(closes_at) => patch({ closes_at })} disabled={disabled || !config.enabled} />
          <label className="text-xs font-medium text-textDim" htmlFor="registration-timezone">Display timezone<input id="registration-timezone" value={config.display_timezone} onChange={(event) => patch({ display_timezone: event.target.value })} className={inputClass} placeholder="Asia/Baghdad" /></label>
          <label className="text-xs font-medium text-textDim" htmlFor="registration-destination">Registration channel ID<input id="registration-destination" value={config.destination_external_id} onChange={(event) => patch({ destination_external_id: event.target.value })} className={inputClass} placeholder="Discord channel ID" /></label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-xs font-medium text-textDim" htmlFor="registration-match">Identity matching
            <select id="registration-match" value={config.gamertag_verification_policy} onChange={(event) => patch({ gamertag_verification_policy: event.target.value as RegistrationConfig['gamertag_verification_policy'] })} className={inputClass}><option value="exact_discord_name">Exact Discord name = Gamertag</option><option value="set_server_nickname">Bot sets server nickname to Gamertag</option><option value="match_or_set_nickname">Match name or set server nickname</option></select>
          </label>
          <label className="text-xs font-medium text-textDim" htmlFor="registration-image-policy">Player image policy
            <select id="registration-image-policy" value={config.image_policy} onChange={(event) => patch({ image_policy: event.target.value as RegistrationConfig['image_policy'] })} className={inputClass}><option value="disabled">Disabled</option><option value="optional">Optional</option><option value="required">Required before ready</option></select>
          </label>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex min-h-11 items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-textDim"><input type="checkbox" checked={config.require_provider_registration} onChange={(event) => patch({ require_provider_registration: event.target.checked })} /> Require registration on {providerType === 'startgg' ? 'Start.gg' : 'Challonge'}</label>
          {providerType === 'startgg' && <label className="flex min-h-11 items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-textDim"><input type="checkbox" checked={config.startgg_bio_verification_enabled} onChange={(event) => patch({ startgg_bio_verification_enabled: event.target.checked })} /> Also allow one-time Start.gg bio code verification</label>}
        </div>
        <label className="block text-xs font-medium text-textDim" htmlFor="registration-role">Verified Discord role ID <span className="font-normal">(optional)</span><input id="registration-role" value={config.verified_role_external_id} onChange={(event) => patch({ verified_role_external_id: event.target.value })} className={inputClass} placeholder="Role ID" /></label>
      </fieldset>
      {!config.enabled && <p className="mt-4 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-textDim">Registration stays disabled until you choose a window and enable it.</p>}
      {config.enabled && config.opens_at && config.closes_at && config.opens_at >= config.closes_at && <p role="alert" className="mt-4 text-xs text-red-200">The opening time must be earlier than the closing time.</p>}
    </section>
  );
}

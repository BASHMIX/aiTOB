import React, { useState } from 'react';
import axios from 'axios';
import { resolveAvatarUrl, getProvenanceBadgeClass, getProvenanceLabel } from './presentation';
import type { ProvenanceSource } from './types';
import { countryCode } from '@/utils/country';

export interface CharacterCatalogItem {
  id: string;
  name: string;
  image_url?: string;
  images?: Array<{ url: string; type?: string }>;
}

export interface EntrantPresentationEditorProps {
  entrant: any;
  currentSlug: string;
  currentEventId?: string;
  link?: any;
  override?: any;
  characters?: CharacterCatalogItem[];
  gameName?: string;
  onSave?: (savedOverride: any) => void;
  onReset?: () => void;
  onClose?: () => void;
}

export function EntrantPresentationEditor({
  entrant,
  currentSlug,
  currentEventId,
  link,
  override = {},
  characters = [],
  gameName = '',
  onSave,
  onReset,
  onClose,
}: EntrantPresentationEditorProps) {
  const entrantId = String(entrant.id || '');
  const providerName = entrant.gamertag || entrant.name || '';
  const providerPrefix = entrant.prefix || entrant.team || '';
  const providerCountry = entrant.country || '';
  const providerImages = entrant.participants?.[0]?.user?.images || [];
  const providerAvatar = providerImages.find((img: any) => img.type === 'profile')?.url || providerImages[0]?.url || '';

  // The linked archive profile is durable. A scoped projection is kept in sync
  // for the current event so existing station views update without ambiguity.
  const [displayName, setDisplayName] = useState(
    override.display_name || override.name || link?.display_name || link?.gamer_tag || providerName
  );
  const [prefix, setPrefix] = useState(
    override.prefix || override.team || link?.prefix || link?.team || providerPrefix
  );
  const [country, setCountry] = useState(
    override.country || link?.country || providerCountry
  );
  const [characterId, setCharacterId] = useState(override.character_id || link?.default_character_id || '');
  const [characterName, setCharacterName] = useState(override.character || override.character_name || link?.default_character_name || '');
  const [characterImageUrl, setCharacterImageUrl] = useState(override.character_image_url || link?.default_character_image_url || '');
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Field provenance helpers
  const getNameProvenance = (): ProvenanceSource => {
    if (override.display_name || override.name) return 'entrant_override';
    if (link?.display_name || link?.gamer_tag) return 'player_profile';
    if (providerName) return 'provider_snapshot';
    return 'placeholder';
  };

  const getAvatarProvenance = (): ProvenanceSource => {
    if (override.avatar_url) return 'entrant_override';
    if (link?.avatar_url || link?.avatar_path) return 'player_profile';
    if (providerAvatar) return 'provider_snapshot';
    return 'placeholder';
  };

  const getCharacterProvenance = (): ProvenanceSource => {
    if (override.character || override.character_name || override.character_id) return 'entrant_override';
    if (link?.default_character_id || link?.default_character_name) return 'player_profile';
    return 'placeholder';
  };

  const currentAvatarUrl = resolveAvatarUrl(
    override.avatar_url,
    link?.avatar_url || link?.avatar_path,
    providerAvatar
  );

  const handleCharacterChange = (selectedName: string) => {
    const found = characters.find(c => c.name === selectedName);
    if (found) {
      setCharacterId(found.id);
      setCharacterName(found.name);
      setCharacterImageUrl(found.image_url || found.images?.[0]?.url || '');
    } else {
      setCharacterId('');
      setCharacterName('');
      setCharacterImageUrl('');
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMessage(null);

    const rawCountry = country.trim();
    const normalizedCountry = rawCountry ? countryCode(rawCountry) : '';
    if (rawCountry && !normalizedCountry) {
      setErrorMessage('Please enter a valid country code or English country name (e.g. JO, US, UK, Jordan).');
      setIsSaving(false);
      return;
    }

    const payload: any = {
      name: displayName.trim(),
      display_name: displayName.trim(),
      prefix: prefix.trim(),
      country: normalizedCountry || '',
      tournament_slug: currentSlug,
      event_id: currentEventId || '',
    };

    if (characterId) {
      payload.character_id = characterId;
      payload.character = characterName;
      payload.character_name = characterName;
      payload.character_image_url = characterImageUrl;
    }

    try {
      await axios.patch(`/api/players/overrides/${entrantId}`, payload);
      if (onSave) {
        onSave({ ...override, ...payload });
      }
      if (onClose) {
        onClose();
      }
    } catch (err: any) {
      const msg = err.response?.data?.message || err.response?.data?.detail || 'Failed to save tournament override';
      setErrorMessage(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetToProfile = async () => {
    setIsSaving(true);
    setErrorMessage(null);
    try {
      await axios.delete(`/api/players/overrides/${entrantId}`, {
        params: {
          tournament_slug: currentSlug,
          event_id: currentEventId || '',
        }
      });
      if (onReset) {
        onReset();
      }
      if (onClose) {
        onClose();
      }
    } catch (err: any) {
      const msg = err.response?.data?.message || err.response?.data?.detail || 'Failed to reset override';
      setErrorMessage(msg);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-appDark border border-white/10 rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-5 text-white">
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div>
            <h3 className="text-lg font-bold text-white">Entrant Presentation Settings</h3>
            <p className="text-xs text-textDim">Edits update Player Archive and synchronise this tournament’s presentation.</p>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="text-textDim hover:text-white text-lg font-bold px-2 py-1"
              aria-label="Close"
            >
              ✕
            </button>
          )}
        </div>

        {errorMessage && (
          <div className="bg-red-500/20 border border-red-500/40 text-red-300 text-xs p-3 rounded">
            {errorMessage}
          </div>
        )}

        {/* Header summary with avatar and current source */}
        <div className="flex items-center gap-4 bg-white/5 p-3 rounded-lg border border-white/5">
          <img
            src={currentAvatarUrl}
            alt={displayName || 'Avatar'}
            className="w-12 h-12 rounded-full border border-white/10 object-cover"
          />
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm">{displayName || providerName}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded border uppercase font-bold ${getProvenanceBadgeClass(getNameProvenance())}`}>
                {getProvenanceLabel(getNameProvenance())}
              </span>
            </div>
            <div className="text-xs text-textDim flex items-center gap-2">
              <span>Avatar source:</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded border font-bold ${getProvenanceBadgeClass(getAvatarProvenance())}`}>
                {getProvenanceLabel(getAvatarProvenance())}
              </span>
            </div>
          </div>
        </div>

        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-textDim uppercase mb-1">
              Display Name
            </label>
            <input
              type="text"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder="e.g. GamerTag"
              className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm text-white focus:border-accentYellow focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-textDim uppercase mb-1">
                Team / Prefix
              </label>
              <input
                type="text"
                value={prefix}
                onChange={e => setPrefix(e.target.value)}
                placeholder="e.g. FNC"
                className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm text-white focus:border-accentYellow focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-textDim uppercase mb-1">
                Country
              </label>
              <input
                type="text"
                value={country}
                onChange={e => setCountry(e.target.value)}
                placeholder="e.g. JO, US, Jordan"
                className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm text-white uppercase focus:border-accentYellow focus:outline-none"
              />
            </div>
          </div>

          {/* Character selection */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-semibold text-textDim uppercase">
                {gameName || 'Game'} Character
              </label>
              <span className={`text-[10px] px-1.5 py-0.5 rounded border font-bold ${getProvenanceBadgeClass(getCharacterProvenance())}`}>
                {getProvenanceLabel(getCharacterProvenance())}
              </span>
            </div>
            {characters.length > 0 ? (
              <div className="flex items-center gap-3">
                <select
                  value={characterName}
                  onChange={e => handleCharacterChange(e.target.value)}
                  className="flex-1 bg-black/40 border border-white/10 rounded px-3 py-2 text-sm text-white focus:border-accentYellow focus:outline-none"
                  aria-label="Character Selection"
                >
                  <option value="">Not selected</option>
                  {characters.map(c => (
                    <option key={c.id} value={c.name}>
                      {c.name}
                    </option>
                  ))}
                </select>
                {characterImageUrl && (
                  <img
                    src={characterImageUrl}
                    alt={characterName || 'Character'}
                    className="h-9 w-9 rounded object-contain border border-white/10"
                  />
                )}
              </div>
            ) : (
              <p className="text-xs text-textDim italic">No character catalog available for this event.</p>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex items-center justify-between pt-4 border-t border-white/10">
            <button
              type="button"
              onClick={handleResetToProfile}
              disabled={isSaving}
              className="text-xs text-red-400 hover:text-red-300 font-bold uppercase disabled:opacity-50"
            >
              Reset to Profile
            </button>
            <div className="flex items-center gap-2">
              {onClose && (
                <button
                  type="button"
                  onClick={onClose}
                  disabled={isSaving}
                  className="px-4 py-2 text-xs font-semibold text-textDim hover:text-white rounded bg-white/5 hover:bg-white/10"
                >
                  Cancel
                </button>
              )}
              <button
                type="submit"
                disabled={isSaving}
                className="px-4 py-2 text-xs font-bold text-black bg-accentYellow hover:bg-yellow-400 rounded transition disabled:opacity-50"
              >
                {isSaving ? 'Saving...' : 'Save Player Profile'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

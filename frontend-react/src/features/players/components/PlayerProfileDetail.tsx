import React, { useState, useEffect } from 'react';
import {
  User,
  Gamepad2,
  Trash2,
  Edit3,
  Plus,
  Tag,
  Save,
  Shield,
  Layers,
  Camera,
} from 'lucide-react';
import type {
  PlayerProfileDetailResponse,
  UpdateProfilePayload,
  CreateGameProfilePayload,
  CreateCharacterDefaultPayload,
} from '../types';
import {
  getPlayerProfile,
  updatePlayerProfile,
  deletePlayerProfile,
  createGameProfile,
  createCharacterDefault,
  uploadPlayerProfileAvatar,
} from '../api';
import { PLACEHOLDER_AVATAR } from '../presentation';
import { countryCode, countryFlagUrl } from '@/utils/country';

export interface PlayerProfileDetailProps {
  profileId: string;
  onProfileUpdated?: () => void;
  onProfileDeleted?: () => void;
}

export const PlayerProfileDetail: React.FC<PlayerProfileDetailProps> = ({
  profileId,
  onProfileUpdated,
  onProfileDeleted,
}) => {
  const [profile, setProfile] = useState<PlayerProfileDetailResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Edit Mode state
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editForm, setEditForm] = useState<UpdateProfilePayload>({});
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [avatarUploadBusy, setAvatarUploadBusy] = useState<boolean>(false);

  // New Game Profile dialog state
  const [showAddGame, setShowAddGame] = useState<boolean>(false);
  const [newGameForm, setNewGameForm] = useState<CreateGameProfilePayload>({ game_id: '' });

  // New Character Default dialog state
  const [activeGameProfileId, setActiveGameProfileId] = useState<string | null>(null);
  const [newCharForm, setNewCharForm] = useState<CreateCharacterDefaultPayload>({
    character_id: '',
    character_name: '',
    character_image_url: '',
    is_primary: true,
  });

  const loadDetail = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getPlayerProfile(profileId);
      setProfile(data);
      setEditForm({
        display_name: data.display_name,
        prefix: data.prefix ?? '',
        country: data.country ?? '',
        avatar_url: data.avatar_url ?? '',
        discord_id: data.discord_id ?? '',
        notes: data.notes ?? '',
      });
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (profileId) {
      loadDetail();
      setIsEditing(false);
    }
  }, [profileId]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editForm.display_name?.trim()) return;

    try {
      setIsSaving(true);
      await updatePlayerProfile(profileId, editForm);
      setIsEditing(false);
      await loadDetail();
      onProfileUpdated?.();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to update profile');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteProfile = async () => {
    if (!window.confirm(`Are you sure you want to delete profile "${profile?.display_name}"?`)) {
      return;
    }
    try {
      setLoading(true);
      await deletePlayerProfile(profileId);
      onProfileDeleted?.();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to delete profile');
      setLoading(false);
    }
  };

  const handleAvatarUpload = async (file: File | undefined) => {
    if (!file) return;
    try {
      setAvatarUploadBusy(true);
      setError(null);
      await uploadPlayerProfileAvatar(profileId, file);
      await loadDetail();
      onProfileUpdated?.();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to upload player photo');
    } finally {
      setAvatarUploadBusy(false);
    }
  };

  const handleAddGameProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGameForm.game_id.trim()) return;

    try {
      await createGameProfile(profileId, newGameForm);
      setNewGameForm({ game_id: '', in_game_name: '', in_game_id: '' });
      setShowAddGame(false);
      await loadDetail();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to add game profile');
    }
  };

  const handleAddCharacterDefault = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeGameProfileId || !newCharForm.character_id.trim() || !newCharForm.character_name.trim()) return;

    try {
      await createCharacterDefault(profileId, activeGameProfileId, newCharForm);
      setNewCharForm({ character_id: '', character_name: '', character_image_url: '', is_primary: true });
      setActiveGameProfileId(null);
      await loadDetail();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to add character default');
    }
  };

  if (loading && !profile) {
    return (
      <div className="flex items-center justify-center p-12 text-zinc-400" data-testid="profile-detail-loading">
        Loading player profile...
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div className="p-6 bg-red-900/20 border border-red-800 rounded-lg text-red-200">
        <p className="font-medium">Error loading profile</p>
        <p className="text-sm mt-1">{error}</p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-zinc-500 border border-dashed border-zinc-800 rounded-lg">
        <User className="w-12 h-12 mb-3 text-zinc-600" />
        <p className="text-sm">Select a player from the list to view profile details.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="player-profile-detail">
      {/* Header Profile Card */}
      <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-[#182334] via-[#111821] to-[#0d1117] p-5 shadow-xl">
        <div className="pointer-events-none absolute -right-14 -top-14 h-40 w-40 rounded-full bg-accentYellow/10 blur-3xl" />
        <div className="flex flex-col sm:flex-row items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="relative h-24 w-24 shrink-0 overflow-hidden rounded-2xl border-2 border-accentYellow/45 bg-zinc-800 shadow-[0_0_25px_rgba(251,191,36,.18)]">
              <img
                src={profile.avatar_url || PLACEHOLDER_AVATAR}
                alt={profile.display_name}
                className="w-full h-full object-cover"
                onError={(e) => {
                  (e.currentTarget as HTMLImageElement).src = PLACEHOLDER_AVATAR;
                }}
              />
              <label className="absolute inset-x-0 bottom-0 flex cursor-pointer items-center justify-center gap-1 bg-black/70 py-1.5 text-[10px] font-bold text-white transition hover:bg-black/90">
                <Camera className="h-3 w-3" /> {avatarUploadBusy ? 'Uploading…' : 'Upload Photo'}
                <input type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" disabled={avatarUploadBusy} onChange={(event) => void handleAvatarUpload(event.target.files?.[0])} />
              </label>
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-[.16em] text-accentYellow">Player profile</p>
              <div className="flex items-center gap-2 flex-wrap">
                {profile.prefix && (
                  <span className="px-2 py-0.5 rounded text-xs font-semibold bg-zinc-800 text-zinc-300 border border-zinc-700">
                    {profile.prefix}
                  </span>
                )}
                <h2 className="text-2xl font-black tracking-tight text-white">{profile.display_name}</h2>
                {profile.country && (
                  <span className="inline-flex items-center gap-1 text-xs text-zinc-200 bg-zinc-800/80 px-2 py-0.5 rounded border border-zinc-700/60">
                    {countryFlagUrl(profile.country) && countryCode(profile.country) ? <img src={countryFlagUrl(profile.country)!} alt={`${countryCode(profile.country)} flag`} title={countryCode(profile.country)!} className="h-3.5 w-5 rounded-[2px] border border-white/15 object-cover" /> : '🏳️'}
                  </span>
                )}
              </div>
              {profile.discord_id && (
                <p className="text-xs text-zinc-400 mt-1 flex items-center gap-1">
                  <Shield className="w-3.5 h-3.5 text-indigo-400" />
                  Discord: <span className="text-zinc-300">{profile.discord_id}</span>
                </p>
              )}
              {profile.notes && (
                <p className="text-xs text-zinc-400 mt-2 italic max-w-lg bg-zinc-950/60 p-2 rounded border border-zinc-800/60">
                  {profile.notes}
                </p>
              )}
            </div>
          </div>

          <div className="relative flex items-center gap-2 self-end sm:self-start">
            <button
              type="button"
              onClick={() => setIsEditing(!isEditing)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-zinc-800 text-zinc-200 hover:bg-zinc-700 transition"
              data-testid="edit-profile-button"
            >
              <Edit3 className="w-3.5 h-3.5" />
              {isEditing ? 'Cancel' : 'Edit Profile'}
            </button>
            <button
              type="button"
              onClick={handleDeleteProfile}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-950/40 text-red-400 border border-red-800/40 hover:bg-red-900/60 transition"
              data-testid="delete-profile-button"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Delete
            </button>
          </div>
        </div>

        {/* Edit Form */}
        {isEditing && (
          <form onSubmit={handleSaveProfile} className="mt-6 pt-6 border-t border-zinc-800 space-y-4">
            <h3 className="text-sm font-semibold text-zinc-200">Edit Profile Information</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Display Name *</label>
                <input
                  type="text"
                  required
                  value={editForm.display_name || ''}
                  onChange={(e) => setEditForm({ ...editForm, display_name: e.target.value })}
                  className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-700 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Prefix / Team</label>
                <input
                  type="text"
                  value={editForm.prefix || ''}
                  onChange={(e) => setEditForm({ ...editForm, prefix: e.target.value })}
                  className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-700 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Country (ISO)</label>
                <input
                  type="text"
                  maxLength={3}
                  value={editForm.country || ''}
                  onChange={(e) => setEditForm({ ...editForm, country: e.target.value.toUpperCase() })}
                  className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-700 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Avatar URL</label>
                <input
                  type="text"
                  value={editForm.avatar_url || ''}
                  onChange={(e) => setEditForm({ ...editForm, avatar_url: e.target.value })}
                  className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-700 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Discord ID / Tag</label>
                <input
                  type="text"
                  value={editForm.discord_id || ''}
                  onChange={(e) => setEditForm({ ...editForm, discord_id: e.target.value })}
                  className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-700 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Notes</label>
                <input
                  type="text"
                  value={editForm.notes || ''}
                  onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                  className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-700 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsEditing(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSaving}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                <Save className="w-3.5 h-3.5" />
                {isSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Game Profiles & Default Characters Section */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Gamepad2 className="w-5 h-5 text-indigo-400" />
            <h3 className="text-base font-semibold text-zinc-100">Game Preferences & Character Defaults</h3>
          </div>
          <button
            type="button"
            onClick={() => setShowAddGame(!showAddGame)}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-600/30 transition"
            data-testid="add-game-profile-button"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Game
          </button>
        </div>

        {/* Add Game Profile Form */}
        {showAddGame && (
          <form onSubmit={handleAddGameProfile} className="p-4 bg-zinc-950/60 border border-zinc-800 rounded-lg space-y-3">
            <h4 className="text-xs font-semibold text-zinc-300">Add Game Configuration</h4>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-[11px] font-medium text-zinc-400 mb-1">Game ID * (e.g. SF6, T8)</label>
                <input
                  type="text"
                  required
                  value={newGameForm.game_id}
                  onChange={(e) => setNewGameForm({ ...newGameForm, game_id: e.target.value })}
                  placeholder="SF6"
                  className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 text-xs text-zinc-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-zinc-400 mb-1">In-Game Name</label>
                <input
                  type="text"
                  value={newGameForm.in_game_name || ''}
                  onChange={(e) => setNewGameForm({ ...newGameForm, in_game_name: e.target.value })}
                  placeholder="Player IGN"
                  className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 text-xs text-zinc-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-zinc-400 mb-1">In-Game ID / CFN</label>
                <input
                  type="text"
                  value={newGameForm.in_game_id || ''}
                  onChange={(e) => setNewGameForm({ ...newGameForm, in_game_id: e.target.value })}
                  placeholder="CFN-123456"
                  className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 text-xs text-zinc-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowAddGame(false)}
                className="px-2.5 py-1 rounded text-xs text-zinc-400 hover:text-zinc-200"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-3 py-1 rounded text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-500"
              >
                Save Game
              </button>
            </div>
          </form>
        )}

        {/* Game Profiles List */}
        {(!profile.game_profiles || profile.game_profiles.length === 0) ? (
          <p className="text-xs text-zinc-500 py-3 italic">
            No game preferences recorded for this player.
          </p>
        ) : (
          <div className="space-y-4">
            {profile.game_profiles.map((gp) => (
              <div key={gp.id} className="p-4 bg-zinc-950/40 border border-zinc-800/80 rounded-xl space-y-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2.5">
                    <span className="px-2.5 py-1 rounded-md text-xs font-bold bg-indigo-950/60 text-indigo-300 border border-indigo-800/40">
                      {gp.game_id}
                    </span>
                    {gp.in_game_name && (
                      <span className="text-sm font-medium text-zinc-200">
                        IGN: <span className="text-zinc-100">{gp.in_game_name}</span>
                      </span>
                    )}
                    {gp.in_game_id && (
                      <span className="text-xs text-zinc-400 bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800">
                        ID: {gp.in_game_id}
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveGameProfileId(activeGameProfileId === gp.id ? null : gp.id)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                  >
                    <Plus className="w-3 h-3" />
                    Add Character
                  </button>
                </div>

                {/* Add Character Form */}
                {activeGameProfileId === gp.id && (
                  <form onSubmit={handleAddCharacterDefault} className="p-3 bg-zinc-900/80 border border-zinc-700/60 rounded-lg space-y-3">
                    <h5 className="text-[11px] font-semibold text-zinc-300">Set Character Default for {gp.game_id}</h5>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      <div>
                        <label className="block text-[10px] text-zinc-400 mb-0.5">Character ID *</label>
                        <input
                          type="text"
                          required
                          placeholder="e.g. ryu"
                          value={newCharForm.character_id}
                          onChange={(e) => setNewCharForm({ ...newCharForm, character_id: e.target.value })}
                          className="w-full px-2 py-1 rounded bg-zinc-950 border border-zinc-700 text-xs text-zinc-100"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-zinc-400 mb-0.5">Character Name *</label>
                        <input
                          type="text"
                          required
                          placeholder="e.g. Ryu"
                          value={newCharForm.character_name}
                          onChange={(e) => setNewCharForm({ ...newCharForm, character_name: e.target.value })}
                          className="w-full px-2 py-1 rounded bg-zinc-950 border border-zinc-700 text-xs text-zinc-100"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-zinc-400 mb-0.5">Image URL</label>
                        <input
                          type="text"
                          placeholder="https://..."
                          value={newCharForm.character_image_url || ''}
                          onChange={(e) => setNewCharForm({ ...newCharForm, character_image_url: e.target.value })}
                          className="w-full px-2 py-1 rounded bg-zinc-950 border border-zinc-700 text-xs text-zinc-100"
                        />
                      </div>
                    </div>
                    <div className="flex items-center justify-between pt-1">
                      <label className="inline-flex items-center gap-1.5 text-xs text-zinc-300 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={newCharForm.is_primary}
                          onChange={(e) => setNewCharForm({ ...newCharForm, is_primary: e.target.checked })}
                          className="rounded border-zinc-700 text-indigo-600 bg-zinc-900"
                        />
                        Primary Main Character
                      </label>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setActiveGameProfileId(null)}
                          className="px-2 py-0.5 text-xs text-zinc-400 hover:text-zinc-200"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="px-2.5 py-1 text-xs font-semibold bg-indigo-600 text-white rounded hover:bg-indigo-500"
                        >
                          Save
                        </button>
                      </div>
                    </div>
                  </form>
                )}

                {/* Characters List */}
                <div className="flex flex-wrap gap-2 pt-1">
                  {(!gp.character_defaults || gp.character_defaults.length === 0) ? (
                    <span className="text-[11px] text-zinc-500 italic">No characters configured.</span>
                  ) : (
                    gp.character_defaults.map((cd) => (
                      <div
                        key={cd.id}
                        className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-200"
                      >
                        {cd.character_image_url ? (
                          <img
                            src={cd.character_image_url}
                            alt={cd.character_name}
                            className="w-5 h-5 rounded object-cover"
                          />
                        ) : (
                          <Tag className="w-3.5 h-3.5 text-zinc-500" />
                        )}
                        <span className="font-medium">{cd.character_name}</span>
                        {cd.is_primary && (
                          <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                            MAIN
                          </span>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Provider Identities Section */}
      {profile.provider_identities && profile.provider_identities.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-sm space-y-3">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-zinc-400" />
            <h3 className="text-sm font-semibold text-zinc-200">Linked Provider Accounts</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {profile.provider_identities.map((id) => (
              <div key={id.id} className="p-3 bg-zinc-950/40 border border-zinc-800 rounded-lg flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold uppercase tracking-wider text-indigo-400">{id.provider}</span>
                  <p className="text-sm text-zinc-200 font-medium">{id.provider_gamer_tag || id.provider_user_id}</p>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Confirmed
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default PlayerProfileDetail;

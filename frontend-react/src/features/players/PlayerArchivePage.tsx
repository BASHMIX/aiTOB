import React, { useState, useEffect } from 'react';
import {
  Users,
  Search,
  Plus,
  RefreshCw,
  Globe,
  User,
  X,
  AlertCircle,
} from 'lucide-react';
import type { PlayerProfile, CreateProfilePayload } from './types';
import { listPlayerProfiles, createPlayerProfile } from './api';
import { PLACEHOLDER_AVATAR } from './presentation';
import PlayerProfileDetail from './components/PlayerProfileDetail';

export const PlayerArchivePage: React.FC = () => {
  const [profiles, setProfiles] = useState<PlayerProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Create Profile Modal
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [createForm, setCreateForm] = useState<CreateProfilePayload>({
    display_name: '',
    prefix: '',
    country: '',
    avatar_url: '',
    discord_id: '',
  });
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const fetchProfiles = async (query = searchQuery) => {
    try {
      setLoading(true);
      setError(null);
      const list = await listPlayerProfiles({ query });
      setProfiles(list);
      // Auto-select first profile if none selected or previous selection deleted
      if (list.length > 0 && (!selectedProfileId || !list.some((p) => p.id === selectedProfileId))) {
        setSelectedProfileId(list[0].id);
      } else if (list.length === 0) {
        setSelectedProfileId(null);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to fetch player profiles');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfiles();
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchProfiles(searchQuery);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.display_name.trim()) return;

    try {
      setIsCreating(true);
      setCreateError(null);
      const created = await createPlayerProfile(createForm);
      setShowCreateModal(false);
      setCreateForm({ display_name: '', prefix: '', country: '', avatar_url: '', discord_id: '' });
      await fetchProfiles();
      setSelectedProfileId(created.id);
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail || 'Failed to create profile');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6" data-testid="player-archive-page">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-zinc-800 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-600/10 text-indigo-400 border border-indigo-500/20">
              <Users className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-zinc-100">Player Archive</h1>
              <p className="text-xs text-zinc-400">
                Persistent player profiles, character defaults, and game preferences across tournaments.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 self-stretch sm:self-auto">
          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-500 transition shadow-sm"
            data-testid="create-profile-button"
          >
            <Plus className="w-4 h-4" />
            New Player Profile
          </button>
        </div>
      </div>

      {/* Main Content Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Sidebar: Search & List */}
        <div className="lg:col-span-4 bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-4">
          <form onSubmit={handleSearchSubmit} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-zinc-400" />
              <input
                type="text"
                placeholder="Search profiles..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
                data-testid="search-profiles-input"
              />
            </div>
            <button
              type="submit"
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition"
            >
              Search
            </button>
            <button
              type="button"
              onClick={() => {
                setSearchQuery('');
                fetchProfiles('');
              }}
              title="Refresh list"
              className="p-1.5 rounded-lg bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </form>

          {/* Profiles List */}
          {loading ? (
            <div className="py-8 text-center text-xs text-zinc-500" data-testid="profiles-loading">
              Loading player archive...
            </div>
          ) : error ? (
            <div className="p-3 bg-red-900/20 border border-red-800 rounded text-xs text-red-300">
              {error}
            </div>
          ) : profiles.length === 0 ? (
            <div className="py-12 text-center text-xs text-zinc-500 border border-dashed border-zinc-800 rounded-lg">
              No player profiles found.
            </div>
          ) : (
            <div className="space-y-1.5 max-h-[600px] overflow-y-auto pr-1" data-testid="profiles-list">
              {profiles.map((p) => {
                const isSelected = p.id === selectedProfileId;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setSelectedProfileId(p.id)}
                    className={`w-full flex items-center justify-between p-2.5 rounded-lg text-left transition border ${
                      isSelected
                        ? 'bg-indigo-950/40 border-indigo-700/60 text-zinc-100 shadow-sm'
                        : 'bg-zinc-950/40 border-zinc-800/60 text-zinc-300 hover:bg-zinc-800/50'
                    }`}
                    data-testid={`profile-item-${p.id}`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-9 h-9 rounded-lg bg-zinc-800 overflow-hidden border border-zinc-700/80 shrink-0">
                        <img
                          src={p.avatar_url || PLACEHOLDER_AVATAR}
                          alt={p.display_name}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.currentTarget as HTMLImageElement).src = PLACEHOLDER_AVATAR;
                          }}
                        />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          {p.prefix && (
                            <span className="text-[10px] font-semibold px-1 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                              {p.prefix}
                            </span>
                          )}
                          <p className="text-xs font-semibold truncate text-zinc-200">{p.display_name}</p>
                        </div>
                        {p.discord_id && (
                          <p className="text-[10px] text-zinc-500 truncate">{p.discord_id}</p>
                        )}
                      </div>
                    </div>

                    {p.country && (
                      <span className="inline-flex items-center gap-1 text-[10px] text-zinc-400 bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800 shrink-0">
                        <Globe className="w-2.5 h-2.5 text-zinc-400" />
                        {p.country}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Detail Pane */}
        <div className="lg:col-span-8">
          {selectedProfileId ? (
            <PlayerProfileDetail
              key={selectedProfileId}
              profileId={selectedProfileId}
              onProfileUpdated={() => fetchProfiles()}
              onProfileDeleted={() => {
                fetchProfiles();
              }}
            />
          ) : (
            <div className="flex flex-col items-center justify-center p-16 bg-zinc-900 border border-zinc-800 rounded-xl text-zinc-500 text-center">
              <User className="w-12 h-12 mb-3 text-zinc-600" />
              <h3 className="text-base font-semibold text-zinc-300">No Profile Selected</h3>
              <p className="text-xs text-zinc-500 mt-1 max-w-sm">
                Choose a profile from the left sidebar or create a new one to manage their details and game preferences.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Create Profile Modal */}
      {showCreateModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs"
          data-testid="create-profile-modal"
        >
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-base font-bold text-zinc-100">Create Player Profile</h3>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="text-zinc-400 hover:text-zinc-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {createError && (
              <div className="p-3 bg-red-900/30 border border-red-800 rounded text-xs text-red-300 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
                <span>{createError}</span>
              </div>
            )}

            <form onSubmit={handleCreateSubmit} className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">Display Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Daigo Umehara"
                  value={createForm.display_name}
                  onChange={(e) => setCreateForm({ ...createForm, display_name: e.target.value })}
                  className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-700 text-xs text-zinc-100 focus:outline-none focus:border-indigo-500"
                  data-testid="create-profile-name-input"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-300 mb-1">Prefix / Team</label>
                  <input
                    type="text"
                    placeholder="e.g. BST"
                    value={createForm.prefix || ''}
                    onChange={(e) => setCreateForm({ ...createForm, prefix: e.target.value })}
                    className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-700 text-xs text-zinc-100 focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-300 mb-1">Country (ISO)</label>
                  <input
                    type="text"
                    maxLength={3}
                    placeholder="e.g. JP"
                    value={createForm.country || ''}
                    onChange={(e) => setCreateForm({ ...createForm, country: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-700 text-xs text-zinc-100 focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">Avatar Image URL</label>
                <input
                  type="text"
                  placeholder="https://..."
                  value={createForm.avatar_url || ''}
                  onChange={(e) => setCreateForm({ ...createForm, avatar_url: e.target.value })}
                  className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-700 text-xs text-zinc-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">Discord ID</label>
                <input
                  type="text"
                  placeholder="e.g. daigo#0001"
                  value={createForm.discord_id || ''}
                  onChange={(e) => setCreateForm({ ...createForm, discord_id: e.target.value })}
                  className="w-full px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-700 text-xs text-zinc-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating}
                  className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
                  data-testid="create-profile-submit"
                >
                  {isCreating ? 'Creating...' : 'Create Profile'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default PlayerArchivePage;

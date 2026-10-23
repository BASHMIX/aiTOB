import React, { useState, useEffect, useRef } from 'react';
import { useHubStore } from '@/store/useHubStore';
import { TopNavigation } from '@/components/layout/TopNavigation';
import { SceneRenderer } from '@/scene/SceneRenderer';
import { ResultsReadiness } from './ResultsReadiness';
import { ResultsExportPanel } from './ResultsExportPanel';
import { ResultsOverlayControls } from './ResultsOverlayControls';
import { STARTER_TEMPLATES } from './templates';
import type { CutoffKind, OutputProfile, SceneDocumentV2, TextNode } from '@/scene/types';
import { usePermission } from '@/hooks/usePermission';
import {
  getLatestEventResults,
  refreshEventResults,
  getResultVersion,
  createMediaOutput,
  recordExportReceipt,
  listResultsStations,
  type MediaOutputResponse,
  type ResultVersionDetail,
  type ResultsStationSummary,
} from './api';
import { downloadPngBlob, exportSceneToPng } from '@/utils/resultsExport';
import { resizeSceneDocument } from '@/scene/resizeScene';

export const ResultsStudioPage: React.FC = () => {
  const { currentSlug, currentEventId, tournaments } = useHubStore();
  const [version, setVersion] = useState<ResultVersionDetail | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [stations, setStations] = useState<ResultsStationSummary[]>([]);
  const [selectedStationId, setSelectedStationId] = useState('');
  const [liveOutput, setLiveOutput] = useState<MediaOutputResponse | null>(null);
  const [isPreparingLive, setIsPreparingLive] = useState(false);
  const [liveError, setLiveError] = useState<string | null>(null);
  const canManageResults = usePermission('results.manage');
  const canBroadcastResults = usePermission('results.broadcast');

  // Template and Scene State
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('champion-focus');
  const [scene, setScene] = useState<SceneDocumentV2>(() => {
    const tpl = STARTER_TEMPLATES.find((t) => t.id === 'champion-focus') || STARTER_TEMPLATES[0];
    return JSON.parse(JSON.stringify(tpl.document));
  });

  const [cutoff, setCutoff] = useState<CutoffKind>('top8');
  const [pageNumber, setPageNumber] = useState(1);
  const [outputProfile, setOutputProfile] = useState<OutputProfile>({
    width: 1920,
    height: 1080,
  });

  const previewContainerRef = useRef<HTMLDivElement>(null);
  const [previewScale, setPreviewScale] = useState<number>(0.5);

  const currentTournament = tournaments.find((t) => t.slug === currentSlug);
  const isChallonge = currentTournament?.provider_type === 'challonge';
  const effectiveEventId = isChallonge ? 'bracket' : currentEventId || 'primary';

  // Load latest results
  const loadLatest = async () => {
    if (!currentSlug) return;
    try {
      const res = await getLatestEventResults(currentSlug, effectiveEventId);
      setVersion(res);
    } catch (err) {
      console.error('Failed to load latest results', err);
      setVersion(null);
    }
  };

  useEffect(() => {
    setVersion(null);
    setPageNumber(1);
    loadLatest();
  }, [currentSlug, effectiveEventId]);

  useEffect(() => {
    if (!canBroadcastResults) {
      setStations([]);
      setSelectedStationId('');
      return;
    }
    let cancelled = false;
    void listResultsStations().then((items) => {
      if (cancelled) return;
      setStations(items);
      setSelectedStationId((current) => current || items[0]?.id || '');
    }).catch((err) => {
      if (!cancelled) setLiveError(err?.response?.data?.detail || 'Failed to load stations');
    });
    return () => { cancelled = true; };
  }, [canBroadcastResults]);

  useEffect(() => {
    setLiveOutput(null);
    setLiveError(null);
  }, [version?.id, cutoff, pageNumber]);

  useEffect(() => {
    if (!version?.id) return;
    let cancelled = false;
    void getResultVersion(version.id, {
      cutoff,
      page: pageNumber,
      page_size: cutoff === 'all' ? 16 : 512,
    }).then((detail) => {
      if (!cancelled) setVersion(detail);
    }).catch((err) => {
      if (!cancelled) setExportError(err?.response?.data?.detail || 'Failed to load the selected standings page');
    });
    return () => { cancelled = true; };
  }, [version?.id, cutoff, pageNumber]);

  useEffect(() => {
    setScene((previous) => {
      const next: SceneDocumentV2 = JSON.parse(JSON.stringify(previous));
      next.dataSource = {
        kind: 'tournament-results',
        resultVersionId: version?.id || null,
      };
      for (const node of Object.values(next.nodes)) {
        if (node.type === 'results-group') {
          node.cutoff = cutoff;
          // version.entries is already the selected server page. Keep the
          // frozen scene on its first local page to avoid applying the offset
          // again in SceneRenderer/OBS.
          node.pageNumber = 1;
          node.pageSize = cutoff === 'all' ? 16 : 512;
        }
      }
      return next;
    });
  }, [version?.id, cutoff, pageNumber]);

  // Template switch
  const handleTemplateChange = (templateId: string) => {
    setSelectedTemplateId(templateId);
    const tpl = STARTER_TEMPLATES.find((t) => t.id === templateId) || STARTER_TEMPLATES[0];
    const newDoc: SceneDocumentV2 = JSON.parse(JSON.stringify(tpl.document));

    // Preserve custom title if user modified it
    const existingTitle = (scene.nodes['doc-header-title'] as TextNode)?.text;
    if (existingTitle && newDoc.nodes['doc-header-title']) {
      (newDoc.nodes['doc-header-title'] as TextNode).text = existingTitle;
    }
    const resizedDoc = resizeSceneDocument(newDoc, outputProfile.width, outputProfile.height);
    resizedDoc.dataSource = { kind: 'tournament-results', resultVersionId: version?.id || null };
    for (const node of Object.values(resizedDoc.nodes)) {
      if (node.type === 'results-group') {
        node.cutoff = cutoff;
        node.pageNumber = 1;
        node.pageSize = cutoff === 'all' ? 16 : 512;
      }
    }

    setScene(resizedDoc);
  };

  // Title edit
  const handleTitleChange = (newTitle: string) => {
    setScene((prev) => {
      const next = JSON.parse(JSON.stringify(prev));
      if (next.nodes['doc-header-title']) {
        (next.nodes['doc-header-title'] as TextNode).text = newTitle;
      }
      return next;
    });
  };

  // Refresh provider standings
  const handleRefresh = async () => {
    if (!currentSlug) return;
    setIsRefreshing(true);
    try {
      await refreshEventResults(currentSlug, effectiveEventId, { force: true });
      await loadLatest();
    } catch (err: any) {
      console.error('Refresh failed', err);
      setExportError(err?.response?.data?.detail || 'Provider results refresh failed');
    } finally {
      setIsRefreshing(false);
    }
  };

  // Export static PNG
  const handleExportPng = async () => {
    if (!version) return;
    setIsExporting(true);
    setExportSuccess(null);
    setExportError(null);

    try {
      const exportTarget = document.getElementById('results-canvas-export-target');
      if (!exportTarget) {
        throw new Error('Canvas export target element not found in DOM.');
      }

      if (version.readiness_state !== 'final') {
        throw new Error('Only a current provider-Final result version can be exported.');
      }

      // Rasterize first. A failed browser render must not create a successful
      // output receipt or trigger a partial download.
      const filename = `${currentSlug}-${effectiveEventId}-${cutoff}-standings.png`;
      const exportRes = await exportSceneToPng(exportTarget, {
        width: outputProfile.width,
        height: outputProfile.height,
        filename,
        skipDownload: true,
      });

      const frozenScene: SceneDocumentV2 = JSON.parse(JSON.stringify(scene));
      frozenScene.canvas.width = outputProfile.width;
      frozenScene.canvas.height = outputProfile.height;
      frozenScene.dataSource = { kind: 'tournament-results', resultVersionId: version.id };

      const output = await createMediaOutput(version.id, {
        output_kind: 'static',
        overlay_name: `${selectedTemplateId} Export`,
        scene: frozenScene,
        cutoff,
        page_number: pageNumber,
        output_profile: outputProfile,
      });

      await recordExportReceipt(output.id, {
        byte_size: exportRes.byteSize,
        sha256: exportRes.sha256,
      });
      downloadPngBlob(exportRes.blob, filename);

      setExportSuccess(`SHA-256: ${exportRes.sha256} (${(exportRes.byteSize / 1024).toFixed(1)} KB)`);
    } catch (err: any) {
      console.error('Export failed', err);
      setExportError(err?.message || 'Failed to export PNG graphic');
    } finally {
      setIsExporting(false);
    }
  };

  const handlePrepareLiveOutput = async () => {
    if (!version || !selectedStationId) return;
    setIsPreparingLive(true);
    setLiveError(null);
    try {
      if (version.readiness_state !== 'final') {
        throw new Error('Only a current provider-Final result version can be taken live.');
      }
      const frozenScene: SceneDocumentV2 = JSON.parse(JSON.stringify(scene));
      frozenScene.canvas.width = outputProfile.width;
      frozenScene.canvas.height = outputProfile.height;
      frozenScene.dataSource = { kind: 'tournament-results', resultVersionId: version.id };
      for (const node of Object.values(frozenScene.nodes)) {
        if (node.type === 'results-group') {
          node.mode = 'sequence';
          node.cutoff = cutoff;
          node.pageNumber = 1;
          node.pageSize = cutoff === 'all' ? 16 : 512;
        }
      }
      const output = await createMediaOutput(version.id, {
        output_kind: 'live',
        overlay_name: `${selectedTemplateId} Live Results`,
        scene: frozenScene,
        cutoff,
        page_number: pageNumber,
        output_profile: outputProfile,
      });
      setLiveOutput(output);
    } catch (err: any) {
      setLiveError(err?.response?.data?.detail || err?.message || 'Failed to prepare live results output');
    } finally {
      setIsPreparingLive(false);
    }
  };

  // Calculate preview scale on container resize
  useEffect(() => {
    const updateScale = () => {
      if (previewContainerRef.current) {
        const containerW = previewContainerRef.current.clientWidth - 48;
        const targetW = scene.canvas.width || 1920;
        const newScale = Math.min(1, Math.max(0.2, containerW / targetW));
        setPreviewScale(newScale);
      }
    };
    updateScale();
    window.addEventListener('resize', updateScale);
    return () => window.removeEventListener('resize', updateScale);
  }, [scene.canvas.width]);

  const currentTitle = (scene.nodes['doc-header-title'] as TextNode)?.text || 'FINAL STANDINGS';
  const handleCutoffChange = (nextCutoff: CutoffKind) => {
    setCutoff(nextCutoff);
    setPageNumber(1);
  };
  const handleProfileChange = (profile: OutputProfile) => {
    setOutputProfile(profile);
    setScene((previous) => resizeSceneDocument(previous, profile.width, profile.height));
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-white flex flex-col">
      <TopNavigation />

      <main className="flex-1 p-6 max-w-[1700px] w-full mx-auto space-y-6">
        {/* Header Bar */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-3">
              <span className="text-blue-500">🏆</span> Results Studio
            </h1>
            <p className="text-xs text-gray-400 mt-1">
              Author and publish verified tournament results graphics and live OBS overlays.
            </p>
          </div>
        </div>

        {/* Readiness Preflight Banner */}
        <ResultsReadiness
          version={version}
          onRefresh={handleRefresh}
          isRefreshing={isRefreshing}
        />

        {/* Stale Version Alert Banner */}
        {version && version.readiness_state === 'stale' && (
          <div className="bg-amber-500/10 border border-amber-500/40 text-amber-200 px-4 py-3 rounded-lg flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="text-base">⚠️</span>
              <span>
                <strong>Stale Result Version:</strong> Provider results or player presentation data have changed since this version was captured.
              </span>
            </div>
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="px-2.5 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded font-semibold text-xs"
            >
              Refresh Version
            </button>
          </div>
        )}

        {/* Studio Workspace Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
          {/* Main Canvas & Customization Column (3 cols) */}
          <div className="lg:col-span-3 space-y-4">
            {/* Customization Toolbar */}
            <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-4 flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div>
                  <label htmlFor="template-select" className="block text-xs font-semibold text-gray-400 mb-1">
                    Template Layout
                  </label>
                  <select
                    id="template-select"
                    aria-label="Template Layout"
                    value={selectedTemplateId}
                    onChange={(e) => handleTemplateChange(e.target.value)}
                    className="bg-[#0d1117] border border-[#30363d] rounded px-3 py-1.5 text-xs text-white focus:border-blue-500 focus:outline-none"
                  >
                    {STARTER_TEMPLATES.map((tpl) => (
                      <option key={tpl.id} value={tpl.id}>
                        {tpl.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="title-input" className="block text-xs font-semibold text-gray-400 mb-1">
                    Header Title
                  </label>
                  <input
                    id="title-input"
                    type="text"
                    value={currentTitle}
                    onChange={(e) => handleTitleChange(e.target.value)}
                    className="bg-[#0d1117] border border-[#30363d] rounded px-3 py-1.5 text-xs text-white focus:border-blue-500 focus:outline-none w-64"
                  />
                </div>
              </div>

              <div className="text-xs text-gray-400 font-mono">
                Preview Zoom: {(previewScale * 100).toFixed(0)}%
              </div>
            </div>

            {/* Canvas Preview Area */}
            <div
              ref={previewContainerRef}
              className="bg-[#161b22] border border-[#30363d] rounded-lg p-6 flex items-center justify-center overflow-auto min-h-[550px] shadow-inner"
            >
              <div
                style={{
                  width: `${(scene.canvas.width || 1920) * previewScale}px`,
                  height: `${(scene.canvas.height || 1080) * previewScale}px`,
                }}
                className="shadow-2xl rounded relative"
              >
                <SceneRenderer
                  scene={scene}
                  standings={version?.entries || []}
                  scale={previewScale}
                />
              </div>
            </div>

            {/* Keep rasterization independent from the responsive preview.
                html-to-image captures computed transforms, so exporting the
                zoomed preview would produce a scaled/cropped PNG.  This
                off-screen canvas remains mounted at the exact output size. */}
            <div
              aria-hidden="true"
              data-testid="results-export-canvas-host"
              style={{
                position: 'fixed',
                left: '-100000px',
                top: 0,
                width: `${scene.canvas.width || 1920}px`,
                height: `${scene.canvas.height || 1080}px`,
                pointerEvents: 'none',
              }}
            >
              <SceneRenderer
                id="results-canvas-export-target"
                scene={scene}
                standings={version?.entries || []}
                scale={1}
              />
            </div>

            {/* Entrant Presentation & Character Provenance Table */}
            {version && version.entries.length > 0 && (
              <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between border-b border-[#30363d] pb-2">
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <span>🎮</span> Entrant Presentation & Featured Characters
                    </h3>
                    <p className="text-xs text-gray-400">
                      Character selection provenance and source tracking for verified standings entries.
                    </p>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="text-gray-400 border-b border-white/5 uppercase text-[10px]">
                        <th className="py-2 px-3">Place</th>
                        <th className="py-2 px-3">Entrant</th>
                        <th className="py-2 px-3">Featured Character</th>
                        <th className="py-2 px-3">Character Source</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {version.entries.map((entry) => {
                        const char = entry.presentation?.character?.value;
                        const source = entry.presentation?.character?.source || 'placeholder';
                        return (
                          <tr key={entry.entrant_id} className="hover:bg-white/5">
                            <td className="py-2 px-3 font-bold text-yellow-400">#{entry.placement}</td>
                            <td className="py-2 px-3 font-semibold text-white">{entry.entrant_name}</td>
                            <td className="py-2 px-3 flex items-center gap-2">
                              {char?.image_url && (
                                <img
                                  src={char.image_url}
                                  alt={char.name || 'Character'}
                                  className="w-5 h-5 object-contain rounded"
                                />
                              )}
                              <span className={char?.name ? 'text-gray-200' : 'text-gray-500 italic'}>
                                {char?.name || 'None'}
                              </span>
                            </td>
                            <td className="py-2 px-3">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
                                  source === 'entrant_override'
                                    ? 'bg-purple-900/40 text-purple-300 border-purple-700/50'
                                    : source === 'player_profile'
                                    ? 'bg-emerald-900/40 text-emerald-300 border-emerald-700/50'
                                    : source === 'provider_snapshot'
                                    ? 'bg-blue-900/40 text-blue-300 border-blue-700/50'
                                    : 'bg-gray-800 text-gray-400 border-gray-700'
                                }`}
                              >
                                {source === 'entrant_override'
                                  ? 'Event Override'
                                  : source === 'player_profile'
                                  ? 'Player Archive'
                                  : source === 'provider_snapshot'
                                  ? 'Provider'
                                  : 'Default'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Right Export Sidebar (1 col) */}
          <div className="lg:col-span-1">
            <ResultsExportPanel
              cutoff={cutoff}
              onCutoffChange={handleCutoffChange}
              outputProfile={outputProfile}
              onProfileChange={handleProfileChange}
              onExport={handleExportPng}
              isExporting={isExporting}
              exportSuccessMessage={exportSuccess}
              exportErrorMessage={exportError}
              hasVersion={Boolean(version)}
              canExport={canManageResults && version?.readiness_state === 'final'}
              hasExportPermission={canManageResults}
              page={pageNumber}
              hasMore={version?.page?.has_more || false}
              totalEntries={version?.page?.total_entries || 0}
              onPageChange={setPageNumber}
            />

            <section className="mt-4 bg-[#161b22] border border-[#30363d] rounded-lg p-5 text-white space-y-4">
              <div>
                <h3 className="text-base font-bold">📡 Live Results Overlay</h3>
                <p className="text-xs text-gray-400 mt-1">
                  Freeze this design in Sequence mode, bind it to a station, then operate the OBS result reveal.
                </p>
              </div>

              {!canBroadcastResults ? (
                <p className="text-xs text-amber-300">
                  Your role does not include results.broadcast. Live station controls are hidden.
                </p>
              ) : (
                <>
                  <label htmlFor="results-live-station" className="block text-xs font-semibold text-gray-300">
                    Live Station
                  </label>
                  <select
                    id="results-live-station"
                    value={selectedStationId}
                    onChange={(event) => {
                      setSelectedStationId(event.target.value);
                      setLiveOutput(null);
                    }}
                    className="w-full bg-[#0d1117] border border-[#30363d] rounded px-3 py-2 text-sm"
                  >
                    {stations.length === 0 && <option value="">No stations available</option>}
                    {stations.map((station) => (
                      <option key={station.id} value={station.id}>{station.name}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={handlePrepareLiveOutput}
                    disabled={!selectedStationId || version?.readiness_state !== 'final' || isPreparingLive}
                    className="w-full py-2 px-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-sm font-bold rounded"
                  >
                    {isPreparingLive ? 'Preparing Live Output...' : 'Prepare Live Output'}
                  </button>
                  {liveError && (
                    <div className="p-2 rounded border border-red-800 bg-red-950/50 text-xs text-red-300">
                      {typeof liveError === 'string' ? liveError : JSON.stringify(liveError)}
                    </div>
                  )}
                  {selectedStationId && liveOutput && (
                    <ResultsOverlayControls
                      stationId={selectedStationId}
                      outputId={liveOutput.id}
                      canBroadcast={canBroadcastResults}
                    />
                  )}
                </>
              )}
            </section>
          </div>
        </div>
      </main>
    </div>
  );
};

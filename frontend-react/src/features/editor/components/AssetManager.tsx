import { useState, useEffect } from 'react';
import axios from 'axios';

export function AssetManager({ onSelect }: { onSelect: (url: string) => void }) {
  const [assets, setAssets] = useState<{name: string, url: string}[]>([]);
  const [uploading, setUploading] = useState(false);

  const fetchAssets = async () => {
    try {
      const res = await axios.get('/api/assets');
      setAssets(res.data.assets || []);
    } catch (e) { console.error("Failed to fetch assets"); }
  };

  useEffect(() => {
    fetchAssets();
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    try {
      await axios.post('/api/assets/upload', formData);
      fetchAssets();
    } catch (err: any) {
      console.error("Asset upload failed:", err);
      const errMsg = err.response?.data?.detail || "Upload failed";
      alert(errMsg);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`Delete ${name}?`)) return;
    try {
      await axios.delete(`/api/assets/${name}`);
      fetchAssets();
    } catch (e) {
      alert("Delete failed");
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[#00ffcc] uppercase tracking-wide font-bold text-xs">Images</h3>
        <label className="cursor-pointer bg-[#3a3a3a] hover:bg-[#444] border border-[#555] rounded px-3 py-1 text-[11px] font-bold">
          {uploading ? 'Uploading...' : '+ Upload'}
          <input type="file" className="hidden" onChange={handleUpload} disabled={uploading} accept="image/*" />
        </label>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {assets.map((asset) => (
          <div key={asset.name} className="group relative aspect-square bg-[#111] rounded border border-[#444] hover:border-[#00ffcc] cursor-pointer overflow-hidden" onClick={() => onSelect(asset.url)}>
            <img src={asset.url} alt={asset.name} className="w-full h-full object-contain" />
            <button 
              className="absolute top-0 right-0 bg-red-600 text-white w-5 h-5 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity rounded-bl"
              onClick={(e) => { e.stopPropagation(); handleDelete(asset.name); }}
            >×</button>
          </div>
        ))}
      </div>
      {assets.length === 0 && <p className="text-[#555] text-center py-4 text-xs italic">No assets uploaded yet.</p>}
    </div>
  );
}

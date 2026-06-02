import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useHubStore } from '@/store/useHubStore';

export function LoginPage() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const setHubPassword = useHubStore(state => state.setHubPassword);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      // Test the password against the verify endpoint
      await axios.post('/api/auth/verify', {}, {
        headers: { 'Authorization': `Bearer ${password}` }
      });

      
      // If success, save to store (which updates localStorage)
      setHubPassword(password);
      navigate('/admin/hub');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid password. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-appDark flex items-center justify-center p-4 selection:bg-accentYellow/30">
      {/* Background Glows */}
      <div className="fixed top-0 left-0 w-full h-full overflow-hidden pointer-events-none -z-10">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-accentYellow/10 blur-[120px] rounded-full animate-pulse" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-blue-600/10 blur-[120px] rounded-full animate-pulse [animation-delay:2s]" />
      </div>

      <div className="w-full max-w-md animate-fadeIn">
        <div className="bg-cardDark border border-white/10 rounded-2xl shadow-2xl p-8 backdrop-blur-xl relative overflow-hidden">
          {/* Top accent bar */}
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-accentYellow via-blue-500 to-accentYellow" />
          
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-accentYellow/10 rounded-2xl mb-4 border border-accentYellow/20">
              <span className="text-3xl">🛡️</span>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Tournament Hub</h1>
            <p className="text-textDim text-sm mt-1 italic">Enter Admin Password</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            <div className="space-y-2">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest ml-1">Password</label>
              <input
                type="password"
                autoFocus
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`w-full bg-appDark border ${error ? 'border-statusRed' : 'border-white/10'} rounded-xl px-5 py-3 text-white outline-none focus:border-accentYellow transition-all shadow-inner`}
                placeholder="••••••••"
              />
              {error && (
                <p className="text-statusRed text-xs mt-2 ml-1 flex items-center gap-1 animate-slideDown">
                  <span>⚠️</span> {error}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={isLoading || !password}
              className="w-full bg-accentYellow hover:bg-yellow-500 disabled:opacity-50 disabled:cursor-not-allowed text-black font-bold py-3.5 rounded-xl transition-all shadow-lg shadow-accentYellow/20 active:scale-95 flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin" />
              ) : (
                <>
                  <span>Unlock Hub</span>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-4 h-4">
                    <path d="M5 12h14m-7-7l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </>
              )}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-white/5 text-center">
            <p className="text-[10px] text-gray-600 font-mono uppercase tracking-[0.2em]">
              AI Tournament Organizer v1.0
            </p>
          </div>
        </div>
        
        <p className="text-center text-gray-500 text-[10px] mt-6 px-10 leading-relaxed italic">
          If you don't know the password, check your <span className="text-accentYellow">.env</span> file for <span className="font-bold">HUB_PASSWORD</span>.
        </p>
      </div>
    </div>
  );
}

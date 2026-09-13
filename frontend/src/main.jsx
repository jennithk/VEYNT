import React, { useEffect, useRef, useState } from 'react';
import ReactDOM from 'react-dom/client';
import './styles.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const languages = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'Hindi' },
  { value: 'te', label: 'Telugu' },
];

const languageLabels = Object.fromEntries(languages.map((item) => [item.value, item.label]));

function App() {
  const [section, setSection] = useState('analyze');
  const [language, setLanguage] = useState('auto');
  const [file, setFile] = useState(null);
  const [recording, setRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [token, setToken] = useState(() => localStorage.getItem('ve ynt_token'));
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);

  const request = (path, options = {}) => fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...(options.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });

  const loadHistory = async () => {
    try {
      const response = await request('/analyses');
      if (!response.ok) throw new Error('History could not be loaded.');
      setHistory((await response.json()).items || []);
    } catch (loadError) {
      setError(loadError.message);
    }
  };

  useEffect(() => {
    if (token) loadHistory();
    return () => {
      clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, [token]);

  const signOut = async () => {
    await request('/auth/signout', { method: 'POST' });
    localStorage.removeItem('ve ynt_token');
    setToken(null);
    setHistory([]);
  };

  const startRecording = async () => {
    setError('');
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError('This browser cannot record audio. Upload a recording instead.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => event.data.size && chunksRef.current.push(event.data);
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        setFile(new File([blob], `ve ynt-recording-${Date.now()}.webm`.replace(' ', ''), { type: blob.type }));
        stream.getTracks().forEach((track) => track.stop());
      };
      recorder.start();
      recorderRef.current = recorder;
      streamRef.current = stream;
      setRecording(true);
      setRecordingSeconds(0);
      timerRef.current = setInterval(() => setRecordingSeconds((seconds) => seconds + 1), 1000);
    } catch {
      setError('Microphone access was denied or is unavailable. Check browser permissions and try again.');
    }
  };

  const stopRecording = () => {
    recorderRef.current?.stop();
    clearInterval(timerRef.current);
    setRecording(false);
  };

  const analyze = async () => {
    if (!file) return;
    setStatus('processing');
    setError('');
    setResult(null);
    const body = new FormData();
    body.append('audio', file);
    try {
      const response = await request(`/analyses?language=${language}`, { method: 'POST', body });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'The recording could not be analyzed.');
      let detail;
      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 500));
        const responseDetail = await request(`/analyses/${payload.id}`);
        if (!responseDetail.ok) throw new Error('The analysis result could not be retrieved.');
        detail = await responseDetail.json();
        if (!['QUEUED', 'PROCESSING'].includes(detail.status)) break;
      }
      setResult(detail);
      await loadHistory();
      setStatus(detail.status === 'FAILED' ? 'error' : 'complete');
    } catch (analysisError) {
      setError(analysisError.message);
      setStatus('error');
    }
  };

  const deleteAnalysis = async (id) => {
    const response = await request(`/analyses/${id}`, { method: 'DELETE' });
    if (response.ok) {
      setHistory((items) => items.filter((item) => item.id !== id));
      if (result?.id === id) setResult(null);
    }
  };

  const formatDuration = (seconds) => `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;

  if (!token) return <AuthPanel onAuthenticated={(nextToken) => { localStorage.setItem('ve ynt_token', nextToken); setToken(nextToken); }} />;

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => setSection('analyze')} aria-label="Veynt home"><span className="brand-mark">V</span><span>VEYNT</span></button>
        <span className="descriptor">Voice Authenticity &amp; Verification</span>
        <button className="account-chip" onClick={signOut}>Sign out</button>
      </header>
      <div className="workspace">
        <aside className="sidebar" aria-label="Primary navigation">
          <p className="eyebrow">Workspace</p>
          <button className={section === 'analyze' ? 'nav-item active' : 'nav-item'} onClick={() => setSection('analyze')}>Check a voice</button>
          <button className={section === 'verify' ? 'nav-item active' : 'nav-item'} onClick={() => setSection('verify')}>Verify speaker</button>
          <button className={section === 'history' ? 'nav-item active' : 'nav-item'} onClick={() => setSection('history')}>History <span>{history.length}</span></button>
          <div className="sidebar-note"><strong>Private by default</strong><br />Audio is processed for analysis and is not stored permanently by this client.</div>
        </aside>
        <main className="content">
          {section === 'history' ? <History items={history} onOpen={(item) => { setResult(item); setSection('analyze'); }} onDelete={deleteAnalysis} /> : section === 'verify' ? <VerifyNotice request={request} /> : (
            <>
              <div className="page-heading"><p className="eyebrow">Voice check</p><h1>Is this voice authentic?</h1><p>Analyze a recording for signs commonly associated with synthetic or voice-cloned speech.</p></div>
              <section className="input-layout">
                <div className="panel capture-panel">
                  <div className="panel-heading"><div><p className="eyebrow">1 / Provide audio</p><h2>Record or upload</h2></div><span className={`status-dot ${recording ? 'live' : ''}`}>{recording ? 'Recording' : 'Ready'}</span></div>
                  <div className="capture-actions">
                    <button className={recording ? 'button danger' : 'button primary'} onClick={recording ? stopRecording : startRecording}>{recording ? 'Stop recording' : 'Record from microphone'}</button>
                    <label className="button secondary">Choose audio file<input type="file" accept="audio/wav,audio/mpeg,audio/mp4,audio/aac,audio/webm,.m4a" onChange={(event) => setFile(event.target.files?.[0] || null)} /></label>
                  </div>
                  {recording && <div className="recording-readout"><span className="pulse" /> {formatDuration(recordingSeconds)} <small>Microphone active</small></div>}
                  {file && !recording && <div className="file-preview"><span className="file-icon">AUDIO</span><div><strong>{file.name}</strong><small>{(file.size / 1024 / 1024).toFixed(2)} MB</small></div><button aria-label="Remove selected audio" onClick={() => setFile(null)}>Remove</button></div>}
                  <div className="field-row"><label htmlFor="language">Language</label><select id="language" value={language} onChange={(event) => setLanguage(event.target.value)}>{languages.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div>
                  <button className="button analyze-button" disabled={!file || recording || status === 'processing'} onClick={analyze}>{status === 'processing' ? 'Analyzing recording...' : 'Analyze recording'}</button>
                  {error && <div className="error-message" role="alert">{error}</div>}
                </div>
                <div className="guidance"><p className="eyebrow">Before you begin</p><h3>Better audio gives better evidence.</h3><p>Use a clear recording with at least a few seconds of natural speech. Results are probabilistic and should not be treated as proof of identity.</p><ul><li>Reduce background noise</li><li>Use the original recording when possible</li><li>Verify sensitive requests another way</li></ul></div>
              </section>
              {result && <Result result={result} />}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function AuthPanel({ onAuthenticated }) {
  const [mode, setMode] = useState('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const submit = async (event) => {
    event.preventDefault();
    setError('');
    try {
      const response = await fetch(`${API_URL}/auth/${mode}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || 'Authentication failed.');
      onAuthenticated(body.token);
    } catch (authError) { setError(authError.message); }
  };
  return <main className="auth-shell"><div className="auth-panel"><div className="brand"><span className="brand-mark">V</span><span>VEYNT</span></div><p className="eyebrow">Voice Authenticity &amp; Verification</p><h1>{mode === 'signin' ? 'Welcome back' : 'Create your account'}</h1><p className="auth-copy">Your analysis history is private to your account and available across your devices.</p><form onSubmit={submit}><label>Email<input type="email" value={email} required onChange={(event) => setEmail(event.target.value)} /></label><label>Password<input type="password" value={password} minLength={10} required onChange={(event) => setPassword(event.target.value)} /></label>{error && <div className="error-message" role="alert">{error}</div>}<button className="button primary auth-submit" type="submit">{mode === 'signin' ? 'Sign in' : 'Create account'}</button></form><button className="auth-switch" onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')}>{mode === 'signin' ? 'Need an account? Create one' : 'Already have an account? Sign in'}</button></div></main>;
}

function Result({ result }) {
  const inconclusive = result.status === 'INCONCLUSIVE' || result.status === 'FAILED' || !result.classification || result.classification === 'INCONCLUSIVE';
  const label = inconclusive ? 'Inconclusive' : result.classification === 'LIKELY_SYNTHETIC' ? 'Likely synthetic' : result.classification === 'LIKELY_HUMAN' ? 'Likely human' : 'Inconclusive';
  return <section className="result-panel" aria-live="polite"><div className="result-header"><div><p className="eyebrow">Veynt analysis</p><h2>{label}</h2></div><div className={`result-score ${inconclusive ? 'neutral' : ''}`}>{result.ai_probability == null ? '--' : `${Math.round(result.ai_probability)}%`}<small>AI likelihood</small></div></div><div className="result-grid"><div><p className="eyebrow">Detection confidence</p><strong>{result.detection_confidence == null ? 'Unavailable' : `${Math.round(result.detection_confidence * 100)}%`}</strong></div><div><p className="eyebrow">Risk level</p><strong>{result.risk?.level || 'INCONCLUSIVE'}</strong></div><div><p className="eyebrow">Language</p><strong>{languageLabels[result.transcript?.language || result.language] || result.transcript?.language || result.language || 'Unavailable'}</strong></div></div><div className="signals"><p className="eyebrow">Why Veynt reached this state</p>{(result.signals || []).map((signal) => <p key={signal}>• {signal}</p>)}</div>{result.transcript?.text && <div className="transcript"><p className="eyebrow">Transcript</p><p>{result.transcript.text}</p></div>}<details><summary>View technical details</summary><pre>{JSON.stringify({ model_version: result.model_version, audio_quality: result.audio_quality, duration_seconds: result.duration_seconds, processing_time_ms: result.processing_time_ms }, null, 2)}</pre></details></section>;
}

function History({ items, onOpen, onDelete }) {
  return <div><div className="page-heading"><p className="eyebrow">Workspace</p><h1>Analysis history</h1><p>Your saved result metadata from this device.</p></div><section className="panel history-panel">{items.length === 0 ? <div className="empty-state"><h2>No analyses yet</h2><p>Completed voice checks will appear here.</p></div> : items.map((item) => <div className="history-row" key={item.id}><div><strong>{item.recording_name}</strong><small>{item.language} · {item.classification}</small></div><div><strong>{item.risk?.level || 'INCONCLUSIVE'}</strong><small>{new Date(item.created_at || Date.now()).toLocaleString()}</small></div><button onClick={() => onOpen(item)}>Open</button><button onClick={() => onDelete(item.id)} aria-label={`Delete ${item.recording_name}`}>Delete</button></div>)}</section></div>;
}

function VerifyNotice({ request }) {
  const [reference, setReference] = useState(null);
  const [test, setTest] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const compareVoices = async () => {
    if (!reference || !test) return;
    setLoading(true);
    setError('');
    setResult(null);
    const body = new FormData();
    body.append('reference', reference);
    body.append('test', test);
    try {
      const response = await request('/speaker-verification', { method: 'POST', body });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Speaker verification failed.');
      setResult(payload);
    } catch (verificationError) {
      setError(verificationError.message);
    } finally {
      setLoading(false);
    }
  };

  return <div><div className="page-heading"><p className="eyebrow">Speaker verification</p><h1>Compare two voices</h1><p>Compare a known reference recording with a test recording. This is probabilistic evidence, not absolute identity proof.</p></div><section className="panel verification-panel"><div className="verification-fields"><label className="verification-upload"><span>Reference voice</span><small>Known recording of the speaker</small><input type="file" accept="audio/*,.m4a" onChange={(event) => setReference(event.target.files?.[0] || null)} />{reference && <strong>{reference.name}</strong>}</label><label className="verification-upload"><span>Test voice</span><small>Recording you want to compare</small><input type="file" accept="audio/*,.m4a" onChange={(event) => setTest(event.target.files?.[0] || null)} />{test && <strong>{test.name}</strong>}</label></div><button className="button primary verification-button" disabled={!reference || !test || loading} onClick={compareVoices}>{loading ? 'Comparing voices...' : 'Verify speaker'}</button>{error && <div className="error-message" role="alert">{error}</div>}{result && <div className="verification-result"><p className="eyebrow">Verification result</p><h2>{result.status === 'MATCH' ? 'Likely same speaker' : result.status === 'NO_MATCH' ? 'Likely different speakers' : 'Inconclusive'}</h2><div className="result-grid"><div><p className="eyebrow">Status</p><strong>{result.status}</strong></div><div><p className="eyebrow">Similarity</p><strong>{result.similarity == null ? 'Unavailable' : `${Math.round(result.similarity)}%`}</strong></div><div><p className="eyebrow">Confidence</p><strong>{result.confidence == null ? 'Unavailable' : `${Math.round(result.confidence)}%`}</strong></div></div><p>{result.reason || 'Use this result as supporting evidence alongside the authenticity analysis.'}</p></div>}</section></div>;
}

ReactDOM.createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);

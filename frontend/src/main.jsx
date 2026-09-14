import React, { useEffect, useRef, useState } from 'react';
import ReactDOM from 'react-dom/client';
import './styles.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const TOKEN_KEY = 've ynt_token';

const languages = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'Hindi' },
  { value: 'te', label: 'Telugu' },
];

const languageLabels = Object.fromEntries(
  languages.map((item) => [item.value, item.label])
);

const analysisStatusLabels = {
  idle: 'Ready',
  waiting: 'Waiting',
  processing: 'Analyzing',
  complete: 'Complete',
  error: 'Error',
};

function getResultLabel(aiProbability) {
  if (aiProbability == null || Number.isNaN(aiProbability)) {
    return 'Inconclusive';
  }

  if (aiProbability >= 90) return 'Highly Likely AI';
  if (aiProbability >= 70) return 'Likely AI';
  if (aiProbability >= 30) return 'Inconclusive';
  return 'Likely Human';
}

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
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));

  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);

  // Central API request helper
  const request = async (path, options = {}) => {
    const url = `${API_URL}${path}`;

    console.log('VEYNT API REQUEST:', {
      method: options.method || 'GET',
      url,
    });

    const response = await fetch(url, {
      ...options,
      headers: {
        ...(options.headers || {}),
        ...(token
          ? { Authorization: `Bearer ${token}` }
          : {}),
      },
    });

    console.log('VEYNT API RESPONSE:', {
      status: response.status,
      url,
    });

    return response;
  };

  // Load previous analyses
  const loadHistory = async () => {
    try {
      const response = await request('/analyses');

      if (!response.ok) {
        throw new Error('History could not be loaded.');
      }

      const data = await response.json();
      setHistory(data.items || []);
    } catch (loadError) {
      console.error('HISTORY ERROR:', loadError);
      setError(loadError.message);
    }
  };

  useEffect(() => {
    if (token) {
      loadHistory();
    }

    return () => {
      clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, [token]);

  // Sign out
  const signOut = async () => {
    try {
      await request('/auth/signout', { method: 'POST' });
    } catch (signOutError) {
      console.error('SIGN OUT ERROR:', signOutError);
    }

    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setHistory([]);
    setResult(null);
  };

  // Start microphone recording
  const startRecording = async () => {
    setError('');

    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError(
        'This browser cannot record audio. Upload a recording instead.'
      );
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });

      const recorder = new MediaRecorder(stream);

      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || 'audio/webm',
        });

        const recordedFile = new File(
          [blob],
          `ve ynt-recording-${Date.now()}.webm`.replace(' ', ''),
          {
            type: blob.type,
          }
        );

        console.log('RECORDING CREATED:', recordedFile);

        setFile(recordedFile);
        setStatus('waiting');

        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.start();

      recorderRef.current = recorder;
      streamRef.current = stream;

      setRecording(true);
      setRecordingSeconds(0);

      timerRef.current = setInterval(() => {
        setRecordingSeconds((seconds) => seconds + 1);
      }, 1000);
    } catch (recordingError) {
      console.error('RECORDING ERROR:', recordingError);

      setError(
        'Microphone access was denied or is unavailable. Check browser permissions and try again.'
      );
    }
  };

  // Stop microphone recording
  const stopRecording = () => {
    recorderRef.current?.stop();
    clearInterval(timerRef.current);
    setRecording(false);
  };

  // Analyze uploaded or recorded audio
  const analyze = async () => {
    console.log('====================================');
    console.log('VEYNT ANALYZE BUTTON CLICKED');
    console.log('Selected file:', file);
    console.log('File name:', file?.name);
    console.log('File type:', file?.type);
    console.log('File size:', file?.size);
    console.log('Language:', language);
    console.log('API URL:', API_URL);
    console.log('====================================');

    if (!file) {
      console.error('ANALYSIS STOPPED: No audio file selected.');

      setError('Please select or record an audio file first.');
      return;
    }

    setStatus('processing');
    setError('');
    setResult(null);

    const body = new FormData();
    body.append('audio', file);

    const analysisPath = `/analyses?language=${encodeURIComponent(language)}`;

    console.log('Sending audio to:', `${API_URL}${analysisPath}`);

    try {
      // Submit audio for analysis
      const response = await request(analysisPath, {
        method: 'POST',
        body,
      });

      console.log('Analysis POST status:', response.status);

      const responseText = await response.text();

      console.log('Analysis POST raw response:', responseText);

      let payload;

      try {
        payload = responseText ? JSON.parse(responseText) : {};
      } catch {
        throw new Error(
          `Backend returned an invalid response. HTTP status: ${response.status}`
        );
      }

      console.log('Analysis POST parsed response:', payload);

      if (!response.ok) {
        const backendMessage =
          typeof payload.detail === 'string'
            ? payload.detail
            : Array.isArray(payload.detail)
              ? payload.detail.map((item) => item.msg).join(', ')
              : 'The recording could not be analyzed.';

        throw new Error(backendMessage);
      }

      if (!payload.id) {
        throw new Error(
          'The backend did not return an analysis ID.'
        );
      }

      console.log('Analysis created with ID:', payload.id);

      // Poll the analysis result
      let detail = null;

      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 500));

        const responseDetail = await request(
          `/analyses/${payload.id}`
        );

        const detailText = await responseDetail.text();

        let detailPayload;

        try {
          detailPayload = detailText
            ? JSON.parse(detailText)
            : {};
        } catch {
          throw new Error(
            'The analysis result returned an invalid response.'
          );
        }

        console.log('Analysis result:', detailPayload);

        if (!responseDetail.ok) {
          throw new Error(
            detailPayload.detail ||
              'The analysis result could not be retrieved.'
          );
        }

        detail = detailPayload;

        if (
          !['QUEUED', 'PROCESSING'].includes(
            String(detail.status || '').toUpperCase()
          )
        ) {
          break;
        }
      }

      if (!detail) {
        throw new Error('No analysis result was returned.');
      }

      console.log('FINAL VEYNT REPORT:', detail);

      setResult(detail);

      await loadHistory();

      const finalStatus = String(detail.status || '').toUpperCase();

      setStatus(finalStatus === 'FAILED' ? 'error' : 'complete');
    } catch (analysisError) {
      console.error('====================================');
      console.error('VEYNT ANALYSIS ERROR:', analysisError);
      console.error('====================================');

      setError(
        analysisError.message ||
          'Something went wrong while analyzing the recording.'
      );

      setStatus('error');
    }
  };

  // Delete an analysis
  const deleteAnalysis = async (id) => {
    try {
      const response = await request(`/analyses/${id}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        setHistory((items) => items.filter((item) => item.id !== id));

        if (result?.id === id) {
          setResult(null);
        }
      } else {
        setError('The analysis could not be deleted.');
      }
    } catch (deleteError) {
      console.error('DELETE ANALYSIS ERROR:', deleteError);
      setError(deleteError.message);
    }
  };

  const formatDuration = (seconds) =>
    `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(
      seconds % 60
    ).padStart(2, '0')}`;

  if (!token) {
    return (
      <AuthPanel
        onAuthenticated={(nextToken) => {
          localStorage.setItem(TOKEN_KEY, nextToken);
          setToken(nextToken);
        }}
      />
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <button
          className="brand"
          onClick={() => setSection('analyze')}
          aria-label="Veynt home"
        >
          <span className="brand-mark">V</span>
          <span>VEYNT</span>
        </button>

        <span className="descriptor">
          Voice authenticity &amp; verification
        </span>

        <button className="account-chip" onClick={signOut}>
          Sign out
        </button>
      </header>

      <div className="workspace">
        <aside className="sidebar" aria-label="Primary navigation">
          <p className="eyebrow">Workspace</p>

          <button
            className={
              section === 'analyze'
                ? 'nav-item active'
                : 'nav-item'
            }
            onClick={() => setSection('analyze')}
          >
            Check a voice
          </button>

          <button
            className={
              section === 'verify'
                ? 'nav-item active'
                : 'nav-item'
            }
            onClick={() => setSection('verify')}
          >
            Verify speaker
          </button>

          <button
            className={
              section === 'history'
                ? 'nav-item active'
                : 'nav-item'
            }
            onClick={() => setSection('history')}
          >
            History <span>{history.length}</span>
          </button>

          <div className="sidebar-note">
            <strong>Private by default</strong>
            <br />
            Audio is processed for analysis and is not stored
            permanently by this client.
          </div>
        </aside>

        <main className="content">
          {section === 'history' ? (
            <History
              items={history}
              onOpen={(item) => {
                setResult(item);
                setStatus(
                  String(item.status || '').toUpperCase() === 'FAILED'
                    ? 'error'
                    : 'complete'
                );
                setSection('analyze');
              }}
              onDelete={deleteAnalysis}
            />
          ) : section === 'verify' ? (
            <VerifyNotice request={request} />
          ) : (
            <>
              <div className="page-heading">
                <p className="eyebrow">Voice check</p>
                <h1>Is this voice authentic?</h1>
                <p>
                  Analyze a recording for signs commonly associated
                  with synthetic or voice-cloned speech.
                </p>
              </div>

              <section className="input-layout">
                <div className="panel capture-panel">
                  <div className="panel-heading">
                    <div>
                      <p className="eyebrow">1 / Provide audio</p>
                      <h2>Record or upload</h2>
                    </div>

                    <span
                      className={`status-dot status-${
                        recording ? 'recording' : status
                      }`}
                      aria-label={`System status: ${
                        recording
                          ? 'Recording'
                          : analysisStatusLabels[status]
                      }`}
                    >
                      {recording
                        ? 'Recording'
                        : analysisStatusLabels[status]}
                    </span>
                  </div>

                  <div className="capture-actions">
                    <button
                      type="button"
                      className={
                        recording
                          ? 'button danger'
                          : 'button primary'
                      }
                      onClick={
                        recording ? stopRecording : startRecording
                      }
                    >
                      {recording
                        ? 'Stop recording'
                        : 'Record from microphone'}
                    </button>

                    <label className="button secondary">
                      Choose audio file

                      <input
                        type="file"
                        accept="audio/wav,audio/mpeg,audio/mp4,audio/aac,audio/webm,.m4a"
                        onChange={(event) => {
                          const selectedFile =
                            event.target.files?.[0] || null;

                          console.log(
                            'AUDIO FILE SELECTED:',
                            selectedFile
                          );

                          setFile(selectedFile);
                          setError('');
                          setResult(null);
                          setStatus(
                            selectedFile ? 'waiting' : 'idle'
                          );
                        }}
                      />
                    </label>
                  </div>

                  {recording && (
                    <div className="recording-readout">
                      <span className="pulse" />
                      {formatDuration(recordingSeconds)}
                      <small>Microphone active</small>
                    </div>
                  )}

                  {file && !recording && (
                    <div className="file-preview">
                      <span className="file-icon">AUDIO</span>

                      <div>
                        <strong>{file.name}</strong>
                        <small>
                          {(file.size / 1024 / 1024).toFixed(2)} MB
                        </small>
                      </div>

                      <button
                        type="button"
                        aria-label="Remove selected audio"
                        onClick={() => {
                          setFile(null);
                          setResult(null);
                          setStatus('idle');
                          setError('');
                        }}
                      >
                        Remove
                      </button>
                    </div>
                  )}

                  <div className="field-row">
                    <label htmlFor="language">Language</label>

                    <select
                      id="language"
                      value={language}
                      onChange={(event) =>
                        setLanguage(event.target.value)
                      }
                    >
                      {languages.map((item) => (
                        <option
                          key={item.value}
                          value={item.value}
                        >
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <button
                    type="button"
                    className="button analyze-button"
                    disabled={
                      !file ||
                      recording ||
                      status === 'processing'
                    }
                    onClick={() => {
                      console.log(
                        'ANALYZE BUTTON EVENT FIRED'
                      );
                      analyze();
                    }}
                  >
                    {status === 'processing'
                      ? 'Analyzing recording...'
                      : 'Analyze recording'}
                  </button>

                  {error && (
                    <div className="error-message" role="alert">
                      {error}
                    </div>
                  )}
                </div>

                <div className="guidance">
                  <p className="eyebrow">Before you begin</p>
                  <h3>Better audio gives better evidence.</h3>
                  <p>
                    Use a clear recording with at least a few
                    seconds of natural speech. Results are
                    probabilistic and should not be treated as
                    proof of identity.
                  </p>

                  <ul>
                    <li>Reduce background noise</li>
                    <li>Use the original recording when possible</li>
                    <li>Verify sensitive requests another way</li>
                  </ul>
                </div>
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
      const response = await fetch(
        `${API_URL}/auth/${mode}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            email,
            password,
          }),
        }
      );

      const body = await response.json();

      if (!response.ok) {
        throw new Error(body.detail || 'Authentication failed.');
      }

      onAuthenticated(body.token);
    } catch (authError) {
      setError(authError.message);
    }
  };

  return (
    <main className="auth-shell">
      <div className="auth-panel">
        <div className="brand">
          <span className="brand-mark">V</span>
          <span>VEYNT</span>
        </div>

        <p className="eyebrow">
          Voice Authenticity &amp; Verification
        </p>

        <h1>
          {mode === 'signin'
            ? 'Welcome back'
            : 'Create your account'}
        </h1>

        <p className="auth-copy">
          Your analysis history is private to your account and
          available across your devices.
        </p>

        <form onSubmit={submit}>
          <label>
            Email
            <input
              type="email"
              value={email}
              required
              onChange={(event) =>
                setEmail(event.target.value)
              }
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              minLength={10}
              required
              onChange={(event) =>
                setPassword(event.target.value)
              }
            />
          </label>

          {error && (
            <div className="error-message" role="alert">
              {error}
            </div>
          )}

          <button
            className="button primary auth-submit"
            type="submit"
          >
            {mode === 'signin'
              ? 'Sign in'
              : 'Create account'}
          </button>
        </form>

        <button
          className="auth-switch"
          onClick={() =>
            setMode(mode === 'signin' ? 'signup' : 'signin')
          }
        >
          {mode === 'signin'
            ? 'Need an account? Create one'
            : 'Already have an account? Sign in'}
        </button>
      </div>
    </main>
  );
}

function Result({ result }) {
  const aiProbability =
    result.ai_probability == null
      ? null
      : Number(result.ai_probability);

  const label = getResultLabel(aiProbability);
  const inconclusive = label === 'Inconclusive';

  const detectionConfidence =
    result.detection_confidence == null
      ? null
      : Number(result.detection_confidence);

  const transcriptText =
    result.transcript?.text || result.transcript_text || '';

  const language =
    result.transcript?.language ||
    result.language ||
    'Unavailable';

  const signals = Array.isArray(result.signals)
    ? result.signals
    : [];

  const recommendation =
    result.recommendation ||
    result.risk?.recommendation ||
    result.next_step ||
    '';

  return (
    <section className="result-panel" aria-live="polite">
      <div className="result-header">
        <div>
          <p className="eyebrow">Veynt analysis</p>
          <h2>{label}</h2>
        </div>

        <div
          className={`result-score ${
            inconclusive ? 'neutral' : ''
          }`}
        >
          {aiProbability == null
            ? '--'
            : `${Math.round(aiProbability)}%`}

          <small>AI likelihood</small>
        </div>
      </div>

      <div className="result-grid">
        <div>
          <p className="eyebrow">Detection confidence</p>
          <strong>
            {detectionConfidence == null
              ? 'Unavailable'
              : `${Math.round(
                  detectionConfidence <= 1
                    ? detectionConfidence * 100
                    : detectionConfidence
                )}%`}
          </strong>
        </div>

        <div>
          <p className="eyebrow">Risk level</p>
          <strong>
            {result.risk?.level || 'INCONCLUSIVE'}
          </strong>
        </div>

        <div>
          <p className="eyebrow">Language</p>
          <strong>
            {languageLabels[language] || language}
          </strong>
        </div>
      </div>

      <div className="signals">
        <p className="eyebrow">
          Why Veynt reached this state
        </p>

        {signals.length > 0 ? (
          signals.map((signal, index) => (
            <p key={`${signal}-${index}`}>• {signal}</p>
          ))
        ) : (
          <p>
            • No additional explanation was returned by the
            analysis provider.
          </p>
        )}
      </div>

      {transcriptText && (
        <div className="transcript">
          <p className="eyebrow">Transcript</p>
          <p>{transcriptText}</p>
        </div>
      )}

      {recommendation && (
        <div className="transcript">
          <p className="eyebrow">Recommendation</p>
          <p>{recommendation}</p>
        </div>
      )}

      <details>
        <summary>View technical details</summary>

        <pre>
          {JSON.stringify(
            {
              id: result.id,
              status: result.status,
              classification: result.classification,
              model_version: result.model_version,
              audio_quality: result.audio_quality,
              duration_seconds: result.duration_seconds,
              processing_time_ms: result.processing_time_ms,
              provider: result.provider,
            },
            null,
            2
          )}
        </pre>
      </details>
    </section>
  );
}

function History({ items, onOpen, onDelete }) {
  return (
    <div>
      <div className="page-heading">
        <p className="eyebrow">Workspace</p>
        <h1>Analysis history</h1>
        <p>Your saved result metadata from this device.</p>
      </div>

      <section className="panel history-panel">
        {items.length === 0 ? (
          <div className="empty-state">
            <h2>No analyses yet</h2>
            <p>
              Completed voice checks will appear here.
            </p>
          </div>
        ) : (
          items.map((item) => (
            <div className="history-row" key={item.id}>
              <div>
                <strong>{item.recording_name}</strong>
                <small>
                  {item.language} · {item.classification}
                </small>
              </div>

              <div>
                <strong>
                  {item.risk?.level || 'INCONCLUSIVE'}
                </strong>
                <small>
                  {new Date(
                    item.created_at || Date.now()
                  ).toLocaleString()}
                </small>
              </div>

              <button
                type="button"
                onClick={() => onOpen(item)}
              >
                Open
              </button>

              <button
                type="button"
                onClick={() => onDelete(item.id)}
                aria-label={`Delete ${item.recording_name}`}
              >
                Delete
              </button>
            </div>
          ))
        )}
      </section>
    </div>
  );
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
      const response = await request(
        '/speaker-verification',
        {
          method: 'POST',
          body,
        }
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload.detail || 'Speaker verification failed.'
        );
      }

      setResult(payload);
    } catch (verificationError) {
      setError(verificationError.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-heading">
        <p className="eyebrow">Speaker verification</p>
        <h1>Compare two voices</h1>
        <p>
          Compare a known reference recording with a test
          recording. This is probabilistic evidence, not
          absolute identity proof.
        </p>
      </div>

      <section className="panel verification-panel">
        <div className="verification-fields">
          <label className="verification-upload">
            <span>Reference voice</span>
            <small>Known recording of the speaker</small>

            <input
              type="file"
              accept="audio/*,.m4a"
              onChange={(event) =>
                setReference(
                  event.target.files?.[0] || null
                )
              }
            />

            {reference && <strong>{reference.name}</strong>}
          </label>

          <label className="verification-upload">
            <span>Test voice</span>
            <small>Recording you want to compare</small>

            <input
              type="file"
              accept="audio/*,.m4a"
              onChange={(event) =>
                setTest(event.target.files?.[0] || null)
              }
            />

            {test && <strong>{test.name}</strong>}
          </label>
        </div>

        <button
          type="button"
          className="button primary verification-button"
          disabled={!reference || !test || loading}
          onClick={compareVoices}
        >
          {loading
            ? 'Comparing voices...'
            : 'Verify speaker'}
        </button>

        {error && (
          <div className="error-message" role="alert">
            {error}
          </div>
        )}

        {result && (
          <div className="verification-result">
            <p className="eyebrow">Verification result</p>

            <h2>
              {result.status === 'MATCH'
                ? 'Likely same speaker'
                : result.status === 'NO_MATCH'
                  ? 'Likely different speakers'
                  : 'Inconclusive'}
            </h2>

            <div className="result-grid">
              <div>
                <p className="eyebrow">Status</p>
                <strong>{result.status}</strong>
              </div>

              <div>
                <p className="eyebrow">Similarity</p>
                <strong>
                  {result.similarity == null
                    ? 'Unavailable'
                    : `${Math.round(
                        result.similarity * 100
                      )}%`}
                </strong>
              </div>

              <div>
                <p className="eyebrow">Confidence</p>
                <strong>
                  {result.confidence == null
                    ? 'Unavailable'
                    : `${Math.round(
                        result.confidence * 100
                      )}%`}
                </strong>
              </div>
            </div>

            <p>
              {result.reason ||
                'Use this result as supporting evidence alongside the authenticity analysis.'}
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
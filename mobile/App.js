import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Audio } from 'expo-av';
import * as DocumentPicker from 'expo-document-picker';
import { StatusBar } from 'expo-status-bar';
import * as SecureStore from 'expo-secure-store';

const API_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000/api';

export default function App() {
  const [recording, setRecording] = useState(null);
  const [file, setFile] = useState(null);
  const [language, setLanguage] = useState('auto');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [token, setToken] = useState(null);
  const [authMode, setAuthMode] = useState('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [booting, setBooting] = useState(true);
  const [history, setHistory] = useState([]);

  useEffect(() => { SecureStore.getItemAsync('ve ynt_token').then(setToken).finally(() => setBooting(false)); return () => recording?.stopAndUnloadAsync(); }, [recording]);

  const request = (path, options = {}) => fetch(`${API_URL}${path}`, { ...options, headers: { ...(options.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) } });

  useEffect(() => {
    if (!token) return;
    request('/analyses').then((response) => response.json()).then((body) => setHistory(body.items || [])).catch(() => setError('History could not be loaded.'));
  }, [token]);

  const authenticate = async (event) => {
    event?.preventDefault?.(); setError('');
    try {
      const response = await fetch(`${API_URL}/auth/${authMode}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || 'Authentication failed.');
      await SecureStore.setItemAsync('ve ynt_token', body.token); setToken(body.token);
    } catch (authError) { setError(authError.message); }
  };

  const startRecording = async () => {
    setError('');
    const permission = await Audio.requestPermissionsAsync();
    if (!permission.granted) {
      setError('Microphone permission is required to record audio. You can choose a file instead.');
      return;
    }
    await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
    const created = await Audio.Recording.createAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
    setRecording(created.recording);
  };

  const stopRecording = async () => {
    await recording.stopAndUnloadAsync();
    const uri = recording.getURI();
    setFile(uri ? { uri, name: 've ynt-recording.m4a', type: 'audio/m4a' } : null);
    setRecording(null);
  };

  const chooseFile = async () => {
    const selection = await DocumentPicker.getDocumentAsync({ type: 'audio/*', copyToCacheDirectory: true });
    if (!selection.canceled) setFile(selection.assets[0]);
  };

  const analyze = async () => {
    if (!file) return;
    setBusy(true); setError(''); setResult(null);
    const body = new FormData();
    body.append('audio', { uri: file.uri, name: file.name || 'recording', type: file.mimeType || file.type || 'audio/m4a' });
    try {
      const response = await request(`/analyses?language=${language}`, { method: 'POST', body });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'The recording could not be analyzed.');
      let detail;
      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 500));
        const detailResponse = await request(`/analyses/${payload.id}`);
        detail = await detailResponse.json();
        if (!['QUEUED', 'PROCESSING'].includes(detail.status)) break;
      }
      setResult(detail);
      setHistory((await request('/analyses').then((response) => response.json())).items || []);
    } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  };

  if (booting) return <SafeAreaView style={styles.safe}><ActivityIndicator /></SafeAreaView>;
  if (!token) return <SafeAreaView style={styles.safe}><ScrollView contentContainerStyle={styles.container}><Text style={styles.logo}>V VEYNT</Text><Text style={styles.kicker}>VOICE AUTHENTICITY & VERIFICATION</Text><Text style={styles.title}>{authMode === 'signin' ? 'Welcome back' : 'Create account'}</Text><Text style={styles.body}>Sign in to keep your analysis history synchronized across devices.</Text><View style={styles.panel}><TextInput style={styles.input} placeholder="Email" autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} /><TextInput style={styles.input} placeholder="Password" secureTextEntry value={password} onChangeText={setPassword} /><Pressable style={styles.primary} onPress={authenticate}><Text style={styles.primaryText}>{authMode === 'signin' ? 'Sign in' : 'Create account'}</Text></Pressable>{error && <Text style={styles.error}>{error}</Text>}<Pressable onPress={() => setAuthMode(authMode === 'signin' ? 'signup' : 'signin')}><Text style={styles.link}>{authMode === 'signin' ? 'Need an account? Create one' : 'Already have an account? Sign in'}</Text></Pressable></View></ScrollView></SafeAreaView>;
  return <SafeAreaView style={styles.safe}><StatusBar style="dark" /><ScrollView contentContainerStyle={styles.container}><Text style={styles.logo}>V VEYNT</Text><Pressable onPress={async () => { await SecureStore.deleteItemAsync('ve ynt_token'); setToken(null); }}><Text style={styles.link}>Sign out</Text></Pressable><Text style={styles.kicker}>VOICE AUTHENTICITY & VERIFICATION</Text><Text style={styles.title}>Check a voice</Text><Text style={styles.body}>Record or upload a voice recording to assess signals associated with synthetic speech.</Text><View style={styles.panel}><Pressable style={styles.primary} onPress={recording ? stopRecording : startRecording}><Text style={styles.primaryText}>{recording ? 'Stop recording' : 'Record from microphone'}</Text></Pressable><Pressable style={styles.secondary} onPress={chooseFile}><Text style={styles.secondaryText}>Choose audio file</Text></Pressable>{file && <Text style={styles.file}>{file.name}</Text>}<Text style={styles.label}>Language</Text><View style={styles.languageRow}>{['auto', 'en', 'hi', 'te'].map((value) => <Pressable key={value} onPress={() => setLanguage(value)} style={[styles.language, language === value && styles.languageSelected]}><Text>{value === 'auto' ? 'Auto' : value.toUpperCase()}</Text></Pressable>)}</View><Pressable disabled={!file || busy} style={[styles.primary, (!file || busy) && styles.disabled]} onPress={analyze}>{busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryText}>Analyze recording</Text>}</Pressable>{error && <Text style={styles.error}>{error}</Text>}</View>{result && <View style={styles.result}><Text style={styles.kicker}>VEYNT ANALYSIS</Text><Text style={styles.resultTitle}>{result.classification || 'INCONCLUSIVE'}</Text><Text style={styles.body}>{result.signals?.join('\n') || 'No verified provider result is available.'}</Text></View>}<View style={styles.history}><Text style={styles.kicker}>RECENT ANALYSES</Text>{history.slice(0, 5).map((item) => <Text key={item.id} style={styles.historyItem}>{item.recording_name} · {item.status} · {item.risk?.level || 'INCONCLUSIVE'}</Text>)}</View></ScrollView></SafeAreaView>;
}

const styles = StyleSheet.create({ safe: { flex: 1, backgroundColor: '#f5f6f2' }, container: { padding: 24, paddingTop: 48 }, logo: { color: '#173f3a', fontSize: 22, fontWeight: '700', letterSpacing: 3 }, kicker: { color: '#72827d', fontSize: 11, fontWeight: '700', letterSpacing: 2, marginTop: 28 }, title: { color: '#173f3a', fontSize: 38, fontWeight: '700', marginTop: 12 }, body: { color: '#64736e', fontSize: 16, lineHeight: 25, marginTop: 12 }, panel: { backgroundColor: '#fbfcf9', borderColor: '#d5ded8', borderWidth: 1, marginTop: 28, padding: 20 }, primary: { alignItems: 'center', backgroundColor: '#173f3a', padding: 15, marginTop: 12 }, primaryText: { color: '#fff', fontWeight: '700' }, secondary: { alignItems: 'center', borderColor: '#cbd6d0', borderWidth: 1, padding: 15, marginTop: 10 }, secondaryText: { color: '#264e47', fontWeight: '700' }, disabled: { opacity: .45 }, file: { color: '#53645f', marginTop: 15 }, label: { color: '#53645f', marginTop: 25, fontWeight: '600' }, input: { borderColor: '#cbd6d0', borderWidth: 1, padding: 13, marginTop: 10, backgroundColor: '#fff' }, link: { color: '#35695d', marginTop: 16 }, languageRow: { flexDirection: 'row', gap: 8, marginTop: 10 }, language: { borderColor: '#cbd6d0', borderWidth: 1, padding: 10 }, languageSelected: { backgroundColor: '#e1eee7', borderColor: '#173f3a' }, error: { color: '#8d3d37', marginTop: 15 }, result: { backgroundColor: '#173f3a', padding: 22, marginTop: 28 }, resultTitle: { color: '#f3c969', fontSize: 28, fontWeight: '700', marginTop: 10 }, history: { marginTop: 30 }, historyItem: { color: '#53645f', borderBottomColor: '#d5ded8', borderBottomWidth: 1, paddingVertical: 12 } });

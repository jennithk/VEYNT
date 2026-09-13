# Veynt mobile

This is the native Expo client for iOS and Android. It uses native microphone permissions and document selection, then submits audio to the same FastAPI backend as the web app.

Set `EXPO_PUBLIC_API_URL` to a reachable backend URL before running on a physical device.

```bash
npm install
npx expo start
npx expo run:android
npx expo run:ios
```

For distributable builds, use EAS Build to produce an Android APK/AAB and an iOS archive. The backend still requires configured, verified STT and authenticity providers before it can return model-based results.

/**
 * WebSocket 通信 — 音频发送 / ASR结果 / TTS流式接收
 */

const WS_URL = `ws://${location.hostname}:8765/ws`;

let ws = null;
let reconnectTimer = null;
let reconnectDelay = 500;

let onAsrResultCb = null;
let onTtsChunkCb = null;
let onErrorCb = null;
let onStatusCb = null;

function onAsrResult(cb) { onAsrResultCb = cb; }
function onTtsChunk(cb) { onTtsChunkCb = cb; }
function onError(cb) { onErrorCb = cb; }
function onStatus(cb) { onStatusCb = cb; }

/**
 * Float32Array PCM [-1,1] → Base64 (Int16 LE)
 */
function pcmToBase64(pcm) {
  const int16 = new Int16Array(pcm.length);
  for (let i = 0; i < pcm.length; i++) {
    const s = Math.max(-1, Math.min(1, pcm[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  const bytes = new Uint8Array(int16.buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    reconnectDelay = 500;
    if (onStatusCb) onStatusCb('connected');
    console.log('[WS] connected');
  };

  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      switch (data.type) {
        case 'asr_result':
          if (onAsrResultCb) onAsrResultCb(data.text);
          break;
        case 'audio':
          if (onTtsChunkCb) onTtsChunkCb(data.audio, data.is_final);
          break;
        case 'error':
          console.warn('[WS] server error:', data.message);
          if (onErrorCb) onErrorCb(data.message);
          break;
        default:
          console.log('[WS] unhandled msg type:', data.type);
      }
    } catch (err) {
      console.warn('[WS] parse error:', err);
    }
  };

  ws.onclose = () => {
    if (onStatusCb) onStatusCb('disconnected');
    console.log('[WS] disconnected, reconnect in', reconnectDelay);
    reconnectTimer = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 1.5, 10000);
      connect();
    }, reconnectDelay);
  };

  ws.onerror = () => {}; // onclose fires after this
}

function sendAudio(pcm) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    console.warn('[WS] not connected, dropping audio');
    return false;
  }
  const b64 = pcmToBase64(pcm);
  ws.send(JSON.stringify({ type: 'audio', audio: b64 }));
  return true;
}

function sendImage(base64JPEG) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    console.warn('[WS] not connected, dropping image');
    return false;
  }
  ws.send(JSON.stringify({ type: 'image', image: base64JPEG }));
  return true;
}

function disconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (ws) {
    ws.onclose = null;
    ws.close();
    ws = null;
  }
}

/**
 * WebSocket 通信 — 音频发送 / ASR结果 / TTS流式接收
 */

const WS_URL = `ws://${location.hostname}:8765/ws`;

const MAX_RETRIES = 10;

let ws = null;
let reconnectTimer = null;
let reconnectDelay = 500;
let retryCount = 0;

let onAsrResultCb = null;
let onTtsChunkCb = null;
let onVlmResultCb = null;
let onErrorCb = null;
let onStatusCb = null;

function onAsrResult(cb) { onAsrResultCb = cb; }
function onTtsChunk(cb) { onTtsChunkCb = cb; }
function onVlmResult(cb) { onVlmResultCb = cb; }
function onError(cb) { onErrorCb = cb; }
function onStatus(cb) { onStatusCb = cb; }

/**
 * Float32Array PCM [-1,1] → Base64 (Int16 LE)
 */
function pcmToBase64(pcm) {
  const GAIN = 6.0;  // 关闭 AGC 后补偿麦克风电平
  const int16 = new Int16Array(pcm.length);
  let peak = 0;
  for (let i = 0; i < pcm.length; i++) {
    const s = Math.max(-1, Math.min(1, pcm[i] * GAIN));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    if (Math.abs(s) > peak) peak = Math.abs(s);
  }
  const bytes = new Uint8Array(int16.buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  const b64 = btoa(binary);
  console.log('[PCM] samples=' + pcm.length + ' peak=' + peak.toFixed(3) + ' gain=' + GAIN);
  return b64;
}

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    reconnectDelay = 500;
    retryCount = 0;
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
        case 'vlm_result':
          if (onVlmResultCb) onVlmResultCb(data.text);
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
    if (retryCount >= MAX_RETRIES) {
      console.warn('[WS] max retries exceeded, giving up');
      if (onStatusCb) onStatusCb('error');
      if (onErrorCb) onErrorCb('WebSocket 连接失败，已达最大重试次数');
      return;
    }
    if (onStatusCb) onStatusCb('reconnecting');
    console.log('[WS] disconnected, retry', retryCount + 1, '/', MAX_RETRIES, 'in', reconnectDelay);
    reconnectTimer = setTimeout(() => {
      retryCount++;
      reconnectDelay = Math.min(reconnectDelay * 1.5, 10000);
      connect();
    }, reconnectDelay);
  };

  ws.onerror = (e) => {
    console.warn('[WS] error, readyState:', ws ? ws.readyState : 'null');
  };
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
  retryCount = 0;
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

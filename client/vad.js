/**
 * 音频采集 + 环形缓冲区 — 按键通话模式
 *
 * 按住录音，松开发送。无 VAD 自动检测，彻底消除切段问题。
 * - 5s 环形缓冲区，采样率 16kHz，16bit mono
 * - startRecording() 清空缓冲，stopRecording() 读取 + 噪音裁剪 + 回调
 */

const VAD_SAMPLE_RATE = 16000;
const BUFFER_SIZE = 4096;
const RING_BUFFER_SEC = 10;         // 环形缓冲区 10 秒（最长录音）
const MIN_SPEECH_SEC = 0.4;         // 最短有效语音时长（短于此视为噪声）

let audioCtx = null;
let streamNode = null;
let processor = null;
let ringBuffer = new Float32Array(VAD_SAMPLE_RATE * RING_BUFFER_SEC);
let ringWritePos = 0;
let ringTotalSamples = 0;

let _isRecording = false;
let _recordStartPos = 0;      // ring buffer 中录音开始位置
let _recordStartTime = 0;     // 录音开始时间 (performance.now)
let _recordFrames = 0;

let onSpeechEndCb = null;
let onVolumeCb = null;
let onRecordStateCb = null;   // 录音状态回调 (true/false)
let onDropCb = null;          // 音频被丢弃回调 (reason)
let _volUpdateFrame = 0;

/** 注册语音结束回调 @param {function(Float32Array)} cb */
function onSpeechEnd(cb) { onSpeechEndCb = cb; }

/** 注册音量回调 @param {function(number)} cb */
function onVolume(cb) { onVolumeCb = cb; }

/** 注册录音状态回调 @param {function(boolean)} cb */
function onRecordState(cb) { onRecordStateCb = cb; }

/** 注册丢弃回调 @param {function(string)} cb — reason: too_short / trimmed_empty */
function onDrop(cb) { onDropCb = cb; }

/** 计算 RMS */
function rms(buffer) {
  let sum = 0;
  for (let i = 0; i < buffer.length; i++) sum += buffer[i] * buffer[i];
  return Math.sqrt(sum / buffer.length);
}

/** 往环形缓冲区写入 PCM 数据 */
function ringWrite(samples) {
  const len = samples.length;
  if (ringWritePos + len <= ringBuffer.length) {
    ringBuffer.set(samples, ringWritePos);
  } else {
    const part1 = ringBuffer.length - ringWritePos;
    ringBuffer.set(samples.subarray(0, part1), ringWritePos);
    ringBuffer.set(samples.subarray(part1), 0);
  }
  ringWritePos = (ringWritePos + len) % ringBuffer.length;
  ringTotalSamples += len;
}

/** 从环形缓冲区读取从 startPos 开始的 durationSec 秒音频 */
function ringReadFrom(startPos, durationSec) {
  const count = Math.min(Math.round(VAD_SAMPLE_RATE * durationSec), ringTotalSamples);
  const result = new Float32Array(count);
  if (startPos + count <= ringBuffer.length) {
    result.set(ringBuffer.subarray(startPos, startPos + count));
  } else {
    const part1 = ringBuffer.length - startPos;
    result.set(ringBuffer.subarray(startPos), 0);
    result.set(ringBuffer.subarray(0, count - part1), part1);
  }
  return result;
}

/** 噪音裁剪：相对阈值 + padding（绕口令辅音多，降低阈值避免误删） */
function trimSilence(audio) {
  const noiseWindow = Math.min(Math.round(VAD_SAMPLE_RATE * 0.3), audio.length);
  let noiseSum = 0;
  for (let i = 0; i < noiseWindow; i++) noiseSum += Math.abs(audio[i]);
  const noiseFloor = noiseSum / noiseWindow;
  const trimThresh = Math.max(noiseFloor * 2, 0.00005);
  let trimStart = 0;
  let trimEnd = audio.length;
  while (trimStart < audio.length && Math.abs(audio[trimStart]) < trimThresh) trimStart++;
  while (trimEnd > trimStart && Math.abs(audio[trimEnd - 1]) < trimThresh) trimEnd--;
  const pad = Math.round(VAD_SAMPLE_RATE * 0.2);
  trimStart = Math.max(0, trimStart - pad);
  trimEnd = Math.min(audio.length, trimEnd + pad);
  if (trimEnd > trimStart) {
    return audio.slice(trimStart, trimEnd);
  }
  return audio;
}

/** 开始录音 — 清空缓冲，标记起始位置 */
function startRecording() {
  _isRecording = true;
  _recordStartPos = ringWritePos;
  _recordStartTime = performance.now();
  _recordFrames = 0;
  ringTotalSamples = 0;
  console.log('[PTT] recording started at pos=' + _recordStartPos);
  if (onRecordStateCb) onRecordStateCb(true);
}

/** 停止录音 — 读取缓冲，裁剪，回调 */
function stopRecording() {
  if (!_isRecording) return;
  _isRecording = false;
  if (onRecordStateCb) onRecordStateCb(false);

  const durSec = (performance.now() - _recordStartTime) / 1000;
  console.log('[PTT] recording stopped dur=%.2fs frames=%d', durSec, _recordFrames);

  if (durSec < MIN_SPEECH_SEC) {
    console.log('[PTT] too_short (%.2fs < %.2fs), ignoring', durSec, MIN_SPEECH_SEC);
    if (onDropCb) onDropCb('too_short');
    return;
  }

  if (onSpeechEndCb) {
    let audio = ringReadFrom(_recordStartPos, durSec);
    audio = trimSilence(audio);
    console.log('[PTT] raw=%d trimmed=%d samples', Math.round(durSec * VAD_SAMPLE_RATE), audio.length);
    if (audio.length >= VAD_SAMPLE_RATE * MIN_SPEECH_SEC) {
      onSpeechEndCb(audio);
    } else {
      console.log('[PTT] trimmed_too_short, dropping');
      if (onDropCb) onDropCb('trimmed');
    }
  }
}

/** 处理音频帧 — 持续写环形缓冲，仅录音期间计数 */
function processFrame(samples) {
  ringWrite(samples);
  if (_isRecording) _recordFrames++;

  if (onVolumeCb) {
    _volUpdateFrame++;
    if (_volUpdateFrame % 5 === 0) {
      onVolumeCb(rms(samples));
    }
  }
}

/** 启动音频采集 @param {MediaStream} stream */
function startVAD(stream) {
  stopVAD();  // 先清理旧实例，避免 AudioContext 泄漏（浏览器硬限制 6 个）
  audioCtx = new (window.AudioContext || window.webkitAudioContext)({
    sampleRate: VAD_SAMPLE_RATE,
  });
  const actualRate = audioCtx.sampleRate;
  console.log('[PTT] requested=%dHz actual=%dHz mismatch=%s',
    VAD_SAMPLE_RATE, actualRate, VAD_SAMPLE_RATE !== actualRate ? 'YES' : 'no');

  streamNode = audioCtx.createMediaStreamSource(stream);

  processor = audioCtx.createScriptProcessor(BUFFER_SIZE, 1, 1);
  processor.onaudioprocess = (e) => {
    const input = e.inputBuffer.getChannelData(0);
    if (!processor._rmsLogged) {
      processor._rmsLogged = true;
      let sum = 0;
      for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
      const rms = Math.sqrt(sum / input.length);
      console.log('[PTT] first frame: rms=' + rms.toFixed(5) + ' samples=' + input.length);
    }
    processFrame(new Float32Array(input));
  };
  streamNode.connect(processor);
  processor.connect(audioCtx.destination);
  console.log('[PTT] capture started (buffer=%d ring=%ds)', BUFFER_SIZE, RING_BUFFER_SEC);
  return audioCtx;
}

/** 停止音频采集 */
function stopVAD() {
  if (processor) { processor.disconnect(); processor = null; }
  if (streamNode) { streamNode.disconnect(); streamNode = null; }
  if (audioCtx) { audioCtx.close(); audioCtx = null; }
}

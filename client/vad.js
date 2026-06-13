/**
 * VAD (Voice Activity Detection) + Ring Buffer
 *
 * 基于 RMS 能量检测：
 * - 3s 环形缓冲区，采样率 16kHz，16bit mono
 * - 检测到 start-of-speech 时回溯 300ms
 * - 静音超过 1.5s 判定 end-of-speech，触发 onSpeechEnd 回调
 */

const VAD_SAMPLE_RATE = 16000;
const BUFFER_SIZE = 4096;
const RING_BUFFER_SEC = 3;          // 环形缓冲区 3 秒
const LOOKBACK_SEC = 0.3;           // 回溯 300ms
const SILENCE_TIMEOUT_SEC = 2.0;    // 静音 2.0s 判定结束
const RMS_THRESHOLD = 0.01;         // RMS 能量阈值
const SPEECH_FRAMES_MIN = 3;        // 连续 N 帧高于阈值才判定 speech start
const MIN_SPEECH_SEC = 0.8;         // 最短有效语音时长（短于此视为噪声）

let audioCtx = null;
let streamNode = null;
let processor = null;
let ringBuffer = new Float32Array(VAD_SAMPLE_RATE * RING_BUFFER_SEC);
let ringWritePos = 0;
let ringTotalSamples = 0;

let isSpeaking = false;
let silenceFrames = 0;
let speechFrames = 0;
const silenceFramesMax = (VAD_SAMPLE_RATE / BUFFER_SIZE) * SILENCE_TIMEOUT_SEC;

let speechStartPos = 0;  // ring buffer 中 speech 开始位置
let onSpeechEndCb = null;
let onVolumeCb = null;
let _volUpdateFrame = 0;

/**
 * 注册 speech end 回调
 * @param {function(Float32Array)} cb - 接收 PCM Float32 采样数组
 */
function onSpeechEnd(cb) {
  onSpeechEndCb = cb;
}

/**
 * 注册音量回调（每 5 帧触发一次）
 * @param {function(number)} cb - 接收 RMS 值 [0, 1]
 */
function onVolume(cb) {
  onVolumeCb = cb;
}

/**
 * 计算 RMS
 */
function rms(buffer) {
  let sum = 0;
  for (let i = 0; i < buffer.length; i++) {
    sum += buffer[i] * buffer[i];
  }
  return Math.sqrt(sum / buffer.length);
}

/**
 * 往环形缓冲区写入 PCM 数据
 */
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

/**
 * 从环形缓冲区读取指定秒数的历史数据
 */
function ringRead(seconds) {
  const count = Math.min(VAD_SAMPLE_RATE * seconds, ringTotalSamples);
  const result = new Float32Array(count);
  const start = (ringWritePos - count + ringBuffer.length) % ringBuffer.length;

  if (start + count <= ringBuffer.length) {
    result.set(ringBuffer.subarray(start, start + count));
  } else {
    const part1 = ringBuffer.length - start;
    result.set(ringBuffer.subarray(start), 0);
    result.set(ringBuffer.subarray(0, count - part1), part1);
  }
  return result;
}

/**
 * 处理音频帧
 */
let _speechFrameCount = 0;
let _speechRmsSum = 0;
let _speechRmsPeak = 0;

function processFrame(samples) {
  const energy = rms(samples);
  ringWrite(samples);

  if (onVolumeCb) {
    _volUpdateFrame++;
    if (_volUpdateFrame % 5 === 0) {
      onVolumeCb(energy);
    }
  }

  if (!isSpeaking) {
    if (energy > RMS_THRESHOLD) {
      speechFrames++;
      if (speechFrames >= SPEECH_FRAMES_MIN) {
        // speech start
        isSpeaking = true;
        silenceFrames = 0;
        speechStartPos = ringWritePos;
        _speechFrameCount = 0;
        _speechRmsSum = 0;
        _speechRmsPeak = 0;
        console.log('[VAD] speech_start rms=' + energy.toFixed(4));
      }
    } else {
      speechFrames = 0;
    }
  } else {
    _speechFrameCount++;
    _speechRmsSum += energy;
    if (energy > _speechRmsPeak) _speechRmsPeak = energy;
    if (energy < RMS_THRESHOLD) {
      silenceFrames++;
      if (silenceFrames >= silenceFramesMax) {
        // speech end
        isSpeaking = false;
        speechFrames = 0;
        silenceFrames = 0;
        const avgRms = _speechFrameCount > 0 ? _speechRmsSum / _speechFrameCount : 0;
        console.log('[VAD] speech_end frames=' + _speechFrameCount + ' rms_avg=' + avgRms.toFixed(5) + ' rms_peak=' + _speechRmsPeak.toFixed(5));

        if (onSpeechEndCb) {
          // 回溯 LOOKBACK_SEC + 从 start 到现在的全部音频
          const durSinceStart = (ringWritePos - speechStartPos + ringBuffer.length) % ringBuffer.length / VAD_SAMPLE_RATE;
          const totalSec = Math.min(durSinceStart + LOOKBACK_SEC, RING_BUFFER_SEC);
          if (totalSec >= MIN_SPEECH_SEC) {
            const audio = ringRead(totalSec);
            onSpeechEndCb(audio);
          } else {
            console.log('[VAD] speech_too_short (%.2fs < %.2fs), ignoring', totalSec, MIN_SPEECH_SEC);
          }
        }
      }
    } else {
      silenceFrames = 0;
    }
  }
}

/**
 * 启动 VAD
 * @param {MediaStream} stream - getUserMedia 获取的流
 */
function startVAD(stream) {
  audioCtx = new (window.AudioContext || window.webkitAudioContext)({
    sampleRate: VAD_SAMPLE_RATE,
  });
  const actualRate = audioCtx.sampleRate;
  console.log('[VAD] requested=%dHz actual=%dHz mismatch=%s',
    VAD_SAMPLE_RATE, actualRate, VAD_SAMPLE_RATE !== actualRate ? 'YES' : 'no');

  streamNode = audioCtx.createMediaStreamSource(stream);

  processor = audioCtx.createScriptProcessor(BUFFER_SIZE, 1, 1);
  processor.onaudioprocess = (e) => {
    const input = e.inputBuffer.getChannelData(0);
    // 打印一次 RMS 用于诊断音量
    if (!processor._rmsLogged) {
      processor._rmsLogged = true;
      let sum = 0;
      for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
      const rms = Math.sqrt(sum / input.length);
      console.log('[VAD] first frame: rms=' + rms.toFixed(5) + ' samples=' + input.length);
    }
    processFrame(new Float32Array(input));
  };
  streamNode.connect(processor);
  processor.connect(audioCtx.destination);
  console.log('[VAD] started (buffer=%d)', BUFFER_SIZE);

  return audioCtx;
}

/**
 * 停止 VAD
 */
function stopVAD() {
  if (processor) {
    processor.disconnect();
    processor = null;
  }
  if (streamNode) {
    streamNode.disconnect();
    streamNode = null;
  }
  if (audioCtx) {
    audioCtx.close();
    audioCtx = null;
  }
}

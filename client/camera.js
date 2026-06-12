/**
 * 摄像头截图 + Canvas 压缩 + Base64 编码
 *
 * 从 video 元素截取帧, 缩放到 512x512, JPEG q=0.7, 输出 Base64
 * 供 WebSocket 发送到 VLM 视觉推理
 */

const MAX_SIZE = 512;
const JPEG_QUALITY = 0.7;

/**
 * 从 video 截取一帧, 返回 Base64 JPEG (不含 data: 前缀)
 * @param {HTMLVideoElement} video
 * @returns {string|null} Base64 JPEG 或 null (video 未就绪)
 */
function captureFrame(video) {
  if (!video || video.readyState < 2) {
    console.warn('[Camera] video not ready');
    return null;
  }

  const canvas = document.createElement('canvas');
  canvas.width = MAX_SIZE;
  canvas.height = MAX_SIZE;
  const ctx = canvas.getContext('2d');

  ctx.drawImage(video, 0, 0, MAX_SIZE, MAX_SIZE);

  const dataURL = canvas.toDataURL('image/jpeg', JPEG_QUALITY);
  // dataURL 格式: "data:image/jpeg;base64,xxxx"
  return dataURL.split(',')[1] || null;
}

/**
 * 截取帧并返回完整 dataURL (用于预览)
 * @param {HTMLVideoElement} video
 * @returns {string|null}
 */
function captureDataURL(video) {
  if (!video || video.readyState < 2) return null;
  const canvas = document.createElement('canvas');
  canvas.width = MAX_SIZE;
  canvas.height = MAX_SIZE;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, MAX_SIZE, MAX_SIZE);
  return canvas.toDataURL('image/jpeg', JPEG_QUALITY);
}

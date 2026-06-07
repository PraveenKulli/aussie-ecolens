// src/services/api.js
import axios from 'axios';
import { getIdToken } from './auth';
import { API_BASE } from '../aws-config';

async function authHeaders() {
  const token = await getIdToken();
  return { Authorization: `Bearer ${token}` };
}

// ── Upload ───────────────────────────────────────────────────────────────────

/** Compute SHA-256 checksum of a File object */
export async function sha256(file) {
  const buffer = await file.arrayBuffer();
  const hash   = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
}

/** Step 1: Get pre-signed URL (checks dedup) */
export async function presignUpload(filename, checksum, contentType) {
  const headers = await authHeaders();
  const { data } = await axios.post(`${API_BASE}/upload/presign`,
    { filename, checksum, content_type: contentType },
    { headers },
  );
  return data;
}

/** Step 2: PUT file directly to S3 */
export async function uploadToS3(presignedUrl, file) {
  await axios.put(presignedUrl, file, {
    headers: { 'Content-Type': file.type },
  });
}

/** Step 3: Confirm upload so tagger triggers */
export async function confirmUpload(fileKey, filename, checksum, contentType) {
  const headers = await authHeaders();
  const { data } = await axios.post(`${API_BASE}/upload/confirm`,
    { file_key: fileKey, filename, checksum, content_type: contentType },
    { headers },
  );
  return data;
}

// ── Queries ──────────────────────────────────────────────────────────────────

export async function queryByTags(tags) {
  const headers = await authHeaders();
  const { data } = await axios.post(`${API_BASE}/query/tags`, tags, { headers });
  return data;
}

export async function queryByThumbnail(thumbnailUrl) {
  const headers = await authHeaders();
  const { data } = await axios.post(`${API_BASE}/query/thumbnail`,
    { thumbnail_url: thumbnailUrl }, { headers });
  return data;
}

async function extractVideoFrame(file) {
  return new Promise((resolve) => {
    const video = document.createElement("video");
    video.preload = "auto";
    video.muted = true;
    video.playsInline = true;
    const url = URL.createObjectURL(file);
    video.src = url;
    let done = false;
    const capture = () => {
      if (done) return;
      done = true;
      URL.revokeObjectURL(url);
      try {
        const MAX = 512;
        const scale = Math.min(1, MAX / (video.videoWidth || 512));
        const w = Math.max(1, Math.round((video.videoWidth || 512) * scale));
        const h = Math.max(1, Math.round((video.videoHeight || 288) * scale));
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        canvas.getContext("2d").drawImage(video, 0, 0, w, h);
        canvas.toBlob((blob) => resolve(blob || null), "image/jpeg", 0.6);
      } catch(e) { resolve(null); }
    };
    video.addEventListener("seeked", capture);
    video.addEventListener("loadeddata", () => { video.currentTime = 0.1; });
    video.addEventListener("error", () => { URL.revokeObjectURL(url); resolve(null); });
    setTimeout(() => { if (!done) capture(); }, 8000);
    video.load();
  });
}

export async function queryByFile(file) {
  const headers = await authHeaders();
  let sendFile = file;
  let sendType = file.type;
  let sendName = file.name;
  if (file.type.startsWith("video/")) {
    console.log("Video detected, extracting frame...", file.name, file.size);
    const frame = await extractVideoFrame(file);
    console.log("Frame result:", frame ? frame.size + " bytes" : "NULL");
    if (frame && frame.size < 4000000) {
      sendFile = frame;
      sendType = "image/jpeg";
      sendName = file.name.replace(/\.[^.]+$/, ".jpg");
    }
  }
  const buffer = await sendFile.arrayBuffer();
  const base64 = btoa(new Uint8Array(buffer).reduce((d, b) => d + String.fromCharCode(b), ""));
  console.log("Sending payload size:", base64.length);
  const { data } = await axios.post(`${API_BASE}/query/file`, {
    file_base64:  base64,
    content_type: sendType,
    filename:     sendName,
  }, { headers });
  return data;
}

// ── Tag management ───────────────────────────────────────────────────────────

export async function editTags(urls, tags, operation) {
  const headers = await authHeaders();
  const { data } = await axios.post(`${API_BASE}/tags`,
    { urls, tags, operation }, { headers });
  return data;
}

// ── Delete ───────────────────────────────────────────────────────────────────

export async function deleteFiles(urls) {
  const headers = await authHeaders();
  const { data } = await axios.post(`${API_BASE}/delete`, { urls }, { headers });
  return data;
}

// ── Notifications ─────────────────────────────────────────────────────────────

export async function subscribeNotifications(email, tags) {
  const headers = await authHeaders();
  const { data } = await axios.post(`${API_BASE}/notifications/subscribe`,
    { email, tags }, { headers });
  return data;
}

export async function unsubscribeNotifications(subscriptionArn) {
  const headers = await authHeaders();
  const { data } = await axios.post(`${API_BASE}/notifications/unsubscribe`,
    { subscription_arn: subscriptionArn }, { headers });
  return data;
}

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

export async function queryByFile(file) {
  const headers = await authHeaders();
  const buffer  = await file.arrayBuffer();
  const base64  = btoa(String.fromCharCode(...new Uint8Array(buffer)));
  const { data } = await axios.post(`${API_BASE}/query/file`, {
    file_base64:  base64,
    content_type: file.type,
    filename:     file.name,
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

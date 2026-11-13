const BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(body.detail)
      ? body.detail.map((d) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join("; ")
      : body.detail;
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return body;
}

export const api = {
  get: (path) => request(path),
  post: (path, data) =>
    request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }),
  upload: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/api/datasets/upload", { method: "POST", body: form });
  },
};

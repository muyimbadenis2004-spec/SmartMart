const CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]')?.content || "";

async function api(url, options = {}) {
  const opts = {
    method: options.method || "GET",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": CSRF_TOKEN,
      ...(options.headers || {}),
    },
    credentials: "same-origin",
  };
  if (options.body !== undefined) {
    opts.body = typeof options.body === "string"
      ? options.body : JSON.stringify(options.body);
  }
  const r = await fetch(url, opts);
  const isJson = (r.headers.get("content-type") || "").includes("application/json");
  const data = isJson ? await r.json() : await r.text();
  if (!r.ok) throw new Error((data && data.error) || ("HTTP " + r.status));
  return data;
}

document.querySelectorAll(".flash").forEach(el => {
  setTimeout(() => el.style.display = "none", 4000);
});

/*
 * Return-evidence photo uploader (M9.3), progressive enhancement over the plain return form.
 *
 * Bytes never touch Django (Vercel's 4.5 MB cap): each file asks for a presigned URL and PUTs
 * straight to private R2, then the returned key is added to the form as a hidden input. The
 * server re-fetches, content-sniffs and re-encodes every key on submit, so a posted key is only
 * ever a hint. Without this script the file input carries no name and nothing is uploaded; the
 * rest of the form still submits.
 */
const form = document.querySelector("[data-return-form]");
const panel = form?.querySelector("[data-return-photos]");
const input = document.getElementById("return-photos");
const list = form?.querySelector("[data-photo-list]");

if (form && panel && input && list) {
  const csrf = form.querySelector("[name=csrfmiddlewaretoken]")?.value ?? "";
  const url = panel.dataset.photoUrl;
  panel.hidden = false;

  input.addEventListener("change", async () => {
    for (const file of Array.from(input.files ?? [])) {
      const item = document.createElement("li");
      item.textContent = `Uploading ${file.name}…`;
      list.append(item);
      try {
        const ticket = await postJSON(url, { content_type: file.type, bytes: file.size });
        const put = await fetch(ticket.upload_url, {
          method: ticket.method,
          headers: ticket.headers,
          body: file,
        });
        if (!put.ok) throw new Error("upload failed");

        const hidden = document.createElement("input");
        hidden.type = "hidden";
        hidden.name = "photo_key";
        hidden.value = ticket.key;
        form.append(hidden);
        item.textContent = file.name;
      } catch {
        item.textContent = `${file.name}: could not upload`;
      }
    }
    input.value = "";
  });

  async function postJSON(endpoint, body) {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw Object.assign(new Error("request failed"), { status: response.status });
    return response.json();
  }
}

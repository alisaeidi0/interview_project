// Admin console — list users, approve/deny signup requests, modify roles.
(() => {
  "use strict";

  const body = document.getElementById("users-body");
  const ROLES = ["employee", "admin"];

  function escapeHtml(t) {
    const d = document.createElement("div");
    d.textContent = t == null ? "" : String(t);
    return d.innerHTML;
  }

  async function load() {
    try {
      const res = await fetch("/api/admin/users");
      if (res.status === 401 || res.status === 403) { window.location.href = "/login"; return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      render(await res.json());
    } catch (e) {
      body.innerHTML = `<tr><td colspan="5" class="admin-empty">Failed to load users.</td></tr>`;
      console.error(e);
    }
  }

  function roleSelect(user) {
    const requested = user.requested_role;
    const current = user.role || requested;
    const opts = ROLES.map(
      (r) => `<option value="${r}" ${r === current ? "selected" : ""}>${r}</option>`
    ).join("");
    return `<select data-role-for="${user.id}">${opts}</select>`;
  }

  function actionsCell(user) {
    if (user.status === "pending") {
      return `<div class="admin-actions">
          ${roleSelect(user)}
          <button class="btn-approve" data-approve="${user.id}">Approve</button>
          <button class="btn-deny" data-deny="${user.id}">Deny</button>
        </div>`;
    }
    // Active/denied users: allow changing the granted role (re-approve).
    return `<div class="admin-actions">
        ${roleSelect(user)}
        <button class="btn-approve" data-approve="${user.id}">Update</button>
        ${user.status !== "denied" ? `<button class="btn-deny" data-deny="${user.id}">Revoke</button>` : ""}
      </div>`;
  }

  function render(users) {
    if (!users.length) {
      body.innerHTML = `<tr><td colspan="5" class="admin-empty">No users yet.</td></tr>`;
      return;
    }
    body.innerHTML = users.map((u) => `
      <tr>
        <td><strong>${escapeHtml(u.name)}</strong><br><span class="role-tag">${escapeHtml(u.email)}</span></td>
        <td><span class="role-tag">${escapeHtml(u.requested_role)}</span></td>
        <td>${escapeHtml(u.role || "—")}</td>
        <td><span class="status-pill status-${u.status}">${escapeHtml(u.status)}</span></td>
        <td>${actionsCell(u)}</td>
      </tr>`).join("");
    wire();
  }

  function selectedRole(id) {
    const sel = document.querySelector(`select[data-role-for="${id}"]`);
    return sel ? sel.value : null;
  }

  async function decide(id, decision) {
    const payload = { decision };
    if (decision === "approve") payload.role = selectedRole(id);
    try {
      const res = await fetch(`/api/admin/users/${id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      load(); // refresh
    } catch (e) {
      console.error(e);
      alert("Action failed. Please try again.");
    }
  }

  function wire() {
    body.querySelectorAll("[data-approve]").forEach((b) =>
      b.addEventListener("click", () => decide(b.dataset.approve, "approve")));
    body.querySelectorAll("[data-deny]").forEach((b) =>
      b.addEventListener("click", () => decide(b.dataset.deny, "deny")));
  }

  load();
})();

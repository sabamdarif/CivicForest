/* Show or hide a password, on any field whose wrapper asks for it (P6).
 *
 * The control is built here rather than rendered in the template, because a button that only
 * works with JavaScript should not be on the page when there is none: the field submits either
 * way, and this only saves the customer retyping a password they cannot see.
 */

const icon = (name) =>
  `<svg class="icon" width="18" height="18" aria-hidden="true" focusable="false"><use href="#i-${name}"></use></svg>`;

for (const wrap of document.querySelectorAll("[data-password-toggle]")) {
  const input = wrap.querySelector('input[type="password"]');
  if (!input) continue;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "field__toggle";
  button.setAttribute("aria-pressed", "false");
  button.setAttribute("aria-label", "Show password");
  button.innerHTML = icon("eye");

  button.addEventListener("click", () => {
    const shown = input.type === "text";
    input.type = shown ? "password" : "text";
    button.setAttribute("aria-pressed", String(!shown));
    button.setAttribute("aria-label", shown ? "Show password" : "Hide password");
    button.innerHTML = icon(shown ? "eye" : "eye-off");
  });

  wrap.append(button);
}

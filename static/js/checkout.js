/* Checkout form enhancement (task 3). The form works fully without this: it posts and
 * re-renders, the server validates. This only saves typing:
 *   - shows the new-address fields when the customer isn't using a saved one;
 *   - fills city and state from the pincode via India Post's free public API.
 * Every field stays editable, so a wrong or missing lookup never blocks the order.
 */

const form = document.querySelector("[data-checkout]");

if (form) {
  const picker = form.querySelector("[name=saved_address]");
  const newAddress = form.querySelector("[data-new-address]");

  if (picker && newAddress) {
    const toggle = () => {
      newAddress.hidden = Boolean(picker.value);
    };
    picker.addEventListener("change", toggle);
    toggle();
  }

  const pincode = form.querySelector("[data-pincode]");
  const city = form.querySelector("[data-city]");
  const state = form.querySelector("[data-state]");

  if (pincode && city && state) {
    pincode.addEventListener("change", async () => {
      const value = pincode.value.trim();
      if (!/^[1-9][0-9]{5}$/.test(value)) return;
      try {
        const res = await fetch(`https://api.postalpincode.in/pincode/${value}`);
        const [data] = await res.json();
        const office = data?.PostOffice?.[0];
        if (!office) return;
        // Only fill blanks, so a value the customer already typed is never overwritten.
        if (!city.value) city.value = office.District ?? "";
        if (!state.value) state.value = office.State ?? "";
      } catch {
        /* ignore: the fields stay editable and the server validates either way */
      }
    });
  }
}

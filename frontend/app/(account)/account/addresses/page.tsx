"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  createAddress,
  deleteAddress,
  getAddresses,
  updateAddress,
  type AddressInput,
} from "@/lib/api/account";
import { ApiError } from "@/lib/api/client";
import type { Address } from "@/lib/api/types";
import { AuthError, getSession, reauthenticate, socialLoginUrl } from "@/lib/auth/allauth";

const EMPTY: AddressInput = {
  full_name: "",
  phone: "",
  line1: "",
  line2: "",
  city: "",
  state: "",
  postal_code: "",
  country: "IN",
  is_default: false,
};

export default function AddressesPage() {
  const router = useRouter();
  const [addresses, setAddresses] = useState<Address[] | null>(null);
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [form, setForm] = useState<AddressInput>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Set when the API demanded a fresh login for this action; holds the retry.
  const [reauthRetry, setReauthRetry] = useState<(() => Promise<void>) | null>(null);

  const reload = useCallback(
    () => getAddresses().then(setAddresses).catch(() => setAddresses([])),
    [],
  );

  useEffect(() => {
    getSession()
      .then((s) => {
        if (!s.meta?.is_authenticated) {
          router.replace("/login");
          return;
        }
        return reload();
      })
      .catch(() => router.replace("/login"));
  }, [router, reload]);

  /** Run a mutation; on 403 reauthentication_required stash it for the password prompt. */
  async function guarded(action: () => Promise<void>) {
    setError(null);
    setBusy(true);
    try {
      await action();
      setReauthRetry(null);
    } catch (err) {
      if (err instanceof ApiError && err.code === "reauthentication_required") {
        setReauthRetry(() => action);
      } else if (
        err instanceof ApiError &&
        err.code === "oauth_reauthentication_required"
      ) {
        window.location.assign(socialLoginUrl("google", "/account/addresses"));
      } else {
        setError(err instanceof ApiError ? err.message : "Something went wrong.");
      }
    } finally {
      setBusy(false);
    }
  }

  function startEdit(a: Address) {
    setEditing(a.id);
    setForm({
      full_name: a.full_name,
      phone: a.phone,
      line1: a.line1,
      line2: a.line2,
      city: a.city,
      state: a.state,
      postal_code: a.postal_code,
      country: a.country,
      is_default: a.is_default,
    });
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const id = editing;
    await guarded(async () => {
      if (id === "new") await createAddress(form);
      else if (id) await updateAddress(id, form);
      setEditing(null);
      await reload();
    });
  }

  if (!addresses) {
    return <div className="container-page py-24 text-center text-ink/50">Loading…</div>;
  }

  return (
    <div className="container-page max-w-3xl py-16">
      <p className="eyebrow">My Account</p>
      <h1 className="mt-2 font-serif text-4xl text-ink">Saved addresses</h1>
      <p className="mt-2 text-sm text-ink/60">
        Your default address prefills checkout. Changing a saved address asks you to
        confirm your password.
      </p>

      {error && (
        <p className="mt-6 rounded-sm bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}

      <div className="mt-8 space-y-4">
        {addresses.length === 0 && editing !== "new" && (
          <p className="text-ink/50">No saved addresses yet.</p>
        )}

        {addresses.map((a) =>
          editing === a.id ? (
            <AddressForm
              key={a.id}
              form={form}
              setForm={setForm}
              busy={busy}
              onSubmit={onSubmit}
              onCancel={() => setEditing(null)}
            />
          ) : (
            <div key={a.id} className="rounded-sm border border-black/10 bg-cream p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="text-sm text-ink/80">
                  <p className="font-semibold text-ink">
                    {a.full_name}
                    {a.is_default && (
                      <span className="ml-2 rounded-full bg-gold/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-gold">
                        Default
                      </span>
                    )}
                  </p>
                  <p className="mt-1">
                    {a.line1}
                    {a.line2 ? `, ${a.line2}` : ""}
                  </p>
                  <p>
                    {a.city}, {a.state} {a.postal_code}
                  </p>
                  <p className="mt-1 text-ink/60">{a.phone}</p>
                </div>
                <div className="flex shrink-0 gap-3 text-sm font-semibold">
                  <button
                    type="button"
                    onClick={() => startEdit(a)}
                    className="text-gold hover:underline"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      guarded(async () => {
                        await deleteAddress(a.id);
                        await reload();
                      })
                    }
                    className="text-red-700/80 hover:underline"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ),
        )}

        {editing === "new" ? (
          <AddressForm
            form={form}
            setForm={setForm}
            busy={busy}
            onSubmit={onSubmit}
            onCancel={() => setEditing(null)}
          />
        ) : (
          <button
            type="button"
            onClick={() => {
              setForm({ ...EMPTY, is_default: addresses.length === 0 });
              setEditing("new");
            }}
            className="btn-outline"
          >
            Add address
          </button>
        )}
      </div>

      {reauthRetry && (
        <ReauthPrompt
          onCancel={() => setReauthRetry(null)}
          onConfirmed={async () => {
            const retry = reauthRetry;
            setReauthRetry(null);
            if (retry) await guarded(retry);
          }}
        />
      )}
    </div>
  );
}

function AddressForm({
  form,
  setForm,
  busy,
  onSubmit,
  onCancel,
}: {
  form: AddressInput;
  setForm: React.Dispatch<React.SetStateAction<AddressInput>>;
  busy: boolean;
  onSubmit: (e: React.FormEvent) => void;
  onCancel: () => void;
}) {
  const set = (key: keyof AddressInput) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  return (
    <form
      onSubmit={onSubmit}
      className="space-y-4 rounded-sm border border-black/10 bg-cream p-5"
    >
      <Field label="Full name" value={form.full_name} onChange={set("full_name")} autoComplete="name" />
      <Field label="Phone" value={form.phone} onChange={set("phone")} autoComplete="tel" />
      <Field label="Address line 1" value={form.line1} onChange={set("line1")} autoComplete="address-line1" />
      <Field
        label="Address line 2 (optional)"
        value={form.line2 ?? ""}
        onChange={set("line2")}
        required={false}
        autoComplete="address-line2"
      />
      <div className="grid grid-cols-2 gap-4">
        <Field label="City" value={form.city} onChange={set("city")} autoComplete="address-level2" />
        <Field label="State" value={form.state} onChange={set("state")} autoComplete="address-level1" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Postal code" value={form.postal_code} onChange={set("postal_code")} autoComplete="postal-code" />
        <Field label="Country" value={form.country ?? "IN"} onChange={set("country")} />
      </div>
      <label className="flex items-center gap-2 text-sm text-ink/70">
        <input
          type="checkbox"
          checked={form.is_default ?? false}
          onChange={(e) => setForm((f) => ({ ...f, is_default: e.target.checked }))}
          className="h-4 w-4 accent-gold"
        />
        Use as my default address
      </label>
      <div className="flex items-center gap-4">
        <button type="submit" disabled={busy} className="btn-dark disabled:opacity-60">
          {busy ? "Saving…" : "Save address"}
        </button>
        <button type="button" onClick={onCancel} className="text-sm text-ink/60 hover:text-ink">
          Cancel
        </button>
      </div>
    </form>
  );
}

function Field({
  label,
  value,
  onChange,
  required = true,
  autoComplete,
}: {
  label: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  required?: boolean;
  autoComplete?: string;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-ink">{label}</span>
      <input
        type="text"
        required={required}
        value={value}
        autoComplete={autoComplete}
        onChange={onChange}
        className="input-field mt-1.5"
      />
    </label>
  );
}

/** Password confirmation dialog shown when the API returns reauthentication_required. */
function ReauthPrompt({
  onCancel,
  onConfirmed,
}: {
  onCancel: () => void;
  onConfirmed: () => Promise<void>;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await reauthenticate(password);
      await onConfirmed();
    } catch (err) {
      setError(err instanceof AuthError ? err.message : "Could not verify your password.");
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal/50 px-6">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-4 rounded-md bg-cream p-6 shadow-card"
      >
        <h2 className="font-serif text-xl text-ink">Confirm it&apos;s you</h2>
        <p className="text-sm text-ink/60">
          Enter your password to change a saved address.
        </p>
        <input
          type="password"
          required
          autoFocus
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          className="input-field"
        />
        {error && (
          <p className="rounded-sm bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}
        <div className="flex items-center gap-4">
          <button type="submit" disabled={busy} className="btn-dark disabled:opacity-60">
            {busy ? "Confirming…" : "Confirm"}
          </button>
          <button type="button" onClick={onCancel} className="text-sm text-ink/60 hover:text-ink">
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

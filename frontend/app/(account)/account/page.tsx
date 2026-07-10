"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ArrowRight } from "@/components/ui/icons";
import { getSession, logout, type SessionUser } from "@/lib/auth/allauth";

export default function AccountPage() {
  const router = useRouter();
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSession()
      .then((s) => {
        if (s.meta?.is_authenticated && s.data?.user) {
          setUser(s.data.user);
        } else {
          router.replace("/login");
        }
      })
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  async function onLogout() {
    await logout().catch(() => {});
    router.replace("/login");
    router.refresh();
  }

  if (loading) {
    return <div className="container-page py-24 text-center text-ink/50">Loading…</div>;
  }

  return (
    <div className="container-page py-16">
      <p className="eyebrow">My Account</p>
      <h1 className="mt-2 font-serif text-4xl text-ink">
        Welcome{user?.display ? `, ${user.display}` : " back"}.
      </h1>
      <p className="mt-2 text-ink/60">{user?.email}</p>

      <div className="mt-10 grid gap-4 sm:grid-cols-3">
        {[
          ["Orders", "Track and review your orders", "/account"],
          ["Wishlist", "Items you've saved for later", "/account"],
          ["Addresses", "Manage your delivery addresses", "/account"],
        ].map(([title, body, href]) => (
          <Link
            key={title}
            href={href}
            className="rounded-sm border border-black/10 bg-cream p-6 transition hover:border-charcoal"
          >
            <h2 className="font-serif text-lg text-ink">{title}</h2>
            <p className="mt-1 text-sm text-ink/60">{body}</p>
            <span className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-brand text-gold">
              Open <ArrowRight className="h-3.5 w-3.5" />
            </span>
          </Link>
        ))}
      </div>

      <button type="button" onClick={onLogout} className="btn-outline mt-10">
        Log out
      </button>
    </div>
  );
}

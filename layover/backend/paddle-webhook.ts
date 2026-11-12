// Layover Logbook: Paddle -> Supabase subscription webhook.
// Paddle calls this whenever a subscription starts, renews, changes or ends.
// It checks the message really came from Paddle, then records the user's plan.
//
// Needs one secret, set in Supabase > Edge Functions > Secrets:
//   PADDLE_WEBHOOK_SECRET = the "secret key" of the notification destination in Paddle

const enc = new TextEncoder();

function hex(buf: ArrayBuffer): string {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Compare without leaking timing information
function sameString(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function signatureOk(raw: string, header: string, secret: string): Promise<boolean> {
  let ts = "";
  const sigs: string[] = [];
  for (const part of header.split(";")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    const k = part.slice(0, i).trim(), v = part.slice(i + 1).trim();
    if (k === "ts") ts = v;
    if (k === "h1") sigs.push(v.toLowerCase());
  }
  if (!ts || !sigs.length) return false;
  if (Math.abs(Date.now() / 1000 - Number(ts)) > 60) return false; // too old: possible replay
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mine = hex(await crypto.subtle.sign("HMAC", key, enc.encode(`${ts}:${raw}`)));
  return sigs.some((s) => sameString(s, mine));
}

function adminKey(): string {
  try {
    const k = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}")["default"];
    if (k) return k;
  } catch (_) { /* fall through to the legacy key */ }
  return Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return new Response("ok");
  const secret = Deno.env.get("PADDLE_WEBHOOK_SECRET");
  if (!secret) return new Response("webhook secret not set", { status: 503 });

  const raw = await req.text();
  if (!(await signatureOk(raw, req.headers.get("paddle-signature") ?? "", secret))) {
    return new Response("bad signature", { status: 401 });
  }

  let evt: any;
  try { evt = JSON.parse(raw); } catch (_) { return new Response("bad json", { status: 400 }); }
  if (typeof evt?.event_type !== "string" || !evt.event_type.startsWith("subscription.")) {
    return new Response("ignored"); // only subscription events matter here
  }

  const s = evt.data ?? {};
  const userId = s.custom_data?.user_id;
  if (typeof userId !== "string" || !UUID.test(userId)) {
    console.warn("subscription event without a user id", evt.event_id);
    return new Response("no user"); // 200 so Paddle doesn't retry forever
  }

  const key = adminKey();
  const headers: Record<string, string> = { "Content-Type": "application/json", apikey: key };
  if (!key.startsWith("sb_")) headers.Authorization = `Bearer ${key}`; // legacy keys are sent both ways

  const r = await fetch(`${Deno.env.get("SUPABASE_URL")}/rest/v1/rpc/apply_subscription_event`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      p_user: userId,
      p_status: String(s.status ?? "none"),
      p_plan: s.items?.[0]?.price?.id ?? null,
      p_customer: s.customer_id ?? null,
      p_subscription: s.id ?? null,
      p_period_end: s.current_billing_period?.ends_at ?? null,
      p_cancel_at: s.scheduled_change?.action === "cancel" ? s.scheduled_change.effective_at : null,
      p_at: evt.occurred_at ?? null,
    }),
  });
  if (!r.ok) {
    console.error("could not save subscription", r.status, await r.text());
    return new Response("save failed", { status: 500 }); // Paddle will retry
  }
  return new Response("saved");
});

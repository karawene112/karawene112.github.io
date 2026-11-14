// Layover Logbook: Roster Check reader (Pro feature).
// The app sends up to 4 roster screenshots; this function checks the user is signed in
// and has Pro (when the paywall is on), then asks Claude to turn the pictures into duties.
//
// Needs one secret, set in Supabase > Edge Functions > Secrets:
//   ANTHROPIC_API_KEY = your key from console.anthropic.com
// The function checks the caller's sign-in itself, so it is deployed with JWT verification off.

const MODEL = "claude-sonnet-5-5";
const MAX_IMAGES = 4;
const MAX_IMAGE_B64 = 6_000_000; // ~4.5 MB per picture after base64
const TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (o: unknown, status = 200) =>
  new Response(JSON.stringify(o), { status, headers: { ...cors, "Content-Type": "application/json" } });

function clean(s: unknown, max = 40): string {
  return String(s ?? "").replace(/[^\w\s:+\-./()]/g, "").slice(0, max);
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "method" }, 405);

  const apiKey = Deno.env.get("ANTHROPIC_API_KEY");
  if (!apiKey) return json({ error: "not_configured" }, 503);

  // Who is calling? Only signed-in users may use the reader.
  const auth = req.headers.get("authorization") ?? "";
  const anon = Deno.env.get("SUPABASE_ANON_KEY") ?? req.headers.get("apikey") ?? "";
  if (!/^Bearer\s+\S+/.test(auth)) return json({ error: "signin" }, 401);
  const who = await fetch(`${Deno.env.get("SUPABASE_URL")}/auth/v1/user`, { headers: { apikey: anon, Authorization: auth } });
  if (!who.ok) return json({ error: "signin" }, 401);

  // Do they have Pro? my_plan runs as the caller.
  const planRes = await fetch(`${Deno.env.get("SUPABASE_URL")}/rest/v1/rpc/my_plan`, {
    method: "POST",
    headers: { apikey: anon, Authorization: auth, "Content-Type": "application/json" },
    body: "{}",
  });
  if (planRes.status === 401) return json({ error: "signin" }, 401);
  const plan = planRes.ok ? await planRes.json() : null;
  if (!plan) return json({ error: "plan_unknown" }, 502);
  if (plan.paywall && !plan.pro) return json({ error: "pro" }, 402);

  let body: any;
  try { body = await req.json(); } catch (_) { return json({ error: "bad_json" }, 400); }
  const imgs = Array.isArray(body?.images) ? body.images.slice(0, MAX_IMAGES) : [];
  if (!imgs.length) return json({ error: "no_images" }, 400);
  for (const i of imgs) {
    if (!TYPES.has(i?.type) || typeof i?.data !== "string" || i.data.length > MAX_IMAGE_B64) {
      return json({ error: "bad_image" }, 400);
    }
  }

  const airline = clean(body.airline), base = clean(body.homeBase, 4).toUpperCase();
  const offset = Number(body.homeOffset) || 0, month = clean(body.month, 7);
  const basis = body.timeBasis === "utc" ? "UTC" : body.timeBasis === "local" ? "local time at each airport"
    : 'unknown, decide from the roster (look for "UTC", "Z", "GMT", "LT" or "local")';

  const prompt = `You are reading an airline cabin crew roster from the attached screenshot(s).
Airline: ${airline}. Crew home base: ${base} (UTC${offset >= 0 ? "+" : ""}${offset}). Roster month: ${month}.
Times shown on the roster are: ${basis}.

Return ONLY a JSON array, one object per duty, in date order. Convert every time to UTC ISO 8601 ending in Z, using your knowledge of each airport's UTC offset on that date.
Each object:
{"kind":"FLY"|"SBY-A"|"SBY-H"|"TRN"|"OFF"|"LEAVE",
 "flights":"flight numbers joined by /, or empty",
 "route":"IATA codes joined by -, e.g. DOH-LHR or DOH-KWI-DOH, or empty",
 "reportUtc":"...Z", "lastOnUtc":"...Z or null (on-blocks time of the last sector)", "releaseUtc":"...Z",
 "blockMinutes": integer (sum of sector block times, 0 if none),
 "originUtcOffset": number, "destUtcOffset": number (UTC offset of the last airport of this duty),
 "endsAtHomeBase": true|false,
 "estimated": [names of any fields you had to guess]}
Rules: a return flight on a later day is a separate duty. If report time is missing, use first departure minus 75 minutes. If release is missing, use last arrival plus 30 minutes. If a day shows only OFF/leave, make an OFF or LEAVE object covering that local day. Ignore hotel and transport lines. Don't add duties that aren't on the roster. If the pictures are not a roster, return [].`;

  const content: unknown[] = imgs.map((i: any) => ({ type: "image", source: { type: "base64", media_type: i.type, data: i.data } }));
  content.push({ type: "text", text: prompt });

  let r: Response;
  try {
    r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "x-api-key": apiKey, "anthropic-version": "2023-06-01", "content-type": "application/json" },
      body: JSON.stringify({ model: MODEL, max_tokens: 8000, messages: [{ role: "user", content }] }),
    });
  } catch (_) { return json({ error: "ai_unreachable" }, 502); }
  if (!r.ok) { console.warn("anthropic", r.status, (await r.text()).slice(0, 300)); return json({ error: "ai_error" }, 502); }

  const out = await r.json();
  const text: string = (out?.content ?? []).filter((c: any) => c.type === "text").map((c: any) => c.text).join("");
  const a = text.indexOf("["), b = text.lastIndexOf("]");
  let duties: unknown = [];
  try { duties = a >= 0 && b > a ? JSON.parse(text.slice(a, b + 1)) : []; } catch (_) { return json({ error: "unreadable" }, 422); }
  if (!Array.isArray(duties)) return json({ error: "unreadable" }, 422);
  return json({ duties: duties.slice(0, 120) });
});

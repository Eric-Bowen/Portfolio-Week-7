// Supabase Edge Function: notify-new-contact
//
// Triggered by a database webhook on INSERT into public.contacts.
// It sends an email notification through Resend (https://resend.com).
//
// Required secrets (Supabase Dashboard > Project Settings > Edge Functions > Secrets):
//   RESEND_API_KEY  - your Resend API key
//   WEBHOOK_SECRET  - any random string; must match the x-webhook-secret header
//                     configured on the database webhook
// Optional secrets:
//   NOTIFY_TO       - recipient (default: Bowen.Zhang26@student.xjtlu.edu.cn)
//   NOTIFY_FROM     - sender (default: "Portfolio Contact <onboarding@resend.dev>")

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY");
const NOTIFY_TO = Deno.env.get("NOTIFY_TO") ?? "bowen.zhang26@student.xjtlu.edu.cn";
const NOTIFY_FROM =
  Deno.env.get("NOTIFY_FROM") ?? "Portfolio Contact <onboarding@resend.dev>";
const WEBHOOK_SECRET = Deno.env.get("WEBHOOK_SECRET");

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") {
    return json({ error: "method_not_allowed" }, 405);
  }

  if (!RESEND_API_KEY) {
    return json({ error: "RESEND_API_KEY is not configured" }, 500);
  }

  // Reject anything that does not carry the shared secret.
  if (WEBHOOK_SECRET && req.headers.get("x-webhook-secret") !== WEBHOOK_SECRET) {
    return json({ error: "unauthorized" }, 401);
  }

  let payload: Record<string, any>;
  try {
    payload = await req.json();
  } catch {
    return json({ error: "invalid_json" }, 400);
  }

  // Database webhooks wrap the row in { record: {...} }.
  const record = payload.record ?? payload;

  const name = String(record.name ?? "").trim();
  const email = String(record.email ?? "").trim();
  const message = String(record.message ?? "").trim();

  if (!name || !email || !message) {
    return json({ error: "missing_fields", received: record }, 400);
  }

  const html = `
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#2b2b2b;line-height:1.6">
      <h2 style="margin:0 0 16px;color:#2A9D8F">New message from your portfolio</h2>
      <p><strong>Name:</strong> ${escapeHtml(name)}</p>
      <p><strong>Email:</strong> ${escapeHtml(email)}</p>
      <p><strong>Message:</strong></p>
      <blockquote style="margin:0;padding:12px 16px;background:#f5f2ee;border-left:3px solid #2A9D8F;white-space:pre-wrap">${escapeHtml(
        message,
      )}</blockquote>
      <p style="margin-top:20px;font-size:13px;color:#8a7c72">
        Reply to ${escapeHtml(name)} at ${escapeHtml(email)}.
      </p>
    </div>
  `;

  const text = [
    "New message from your portfolio",
    "",
    `Name: ${name}`,
    `Email: ${email}`,
    "",
    message,
  ].join("\n");

  const resendResponse = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${RESEND_API_KEY}`,
    },
    body: JSON.stringify({
      from: NOTIFY_FROM,
      to: [NOTIFY_TO],
      subject: `New contact message from ${name}`,
      html,
      text,
    }),
  });

  const data = await resendResponse.json().catch(() => ({}));

  if (!resendResponse.ok) {
    console.error("Resend error", resendResponse.status, data);
    return json(
      { error: "email_failed", status: resendResponse.status, details: data },
      500,
    );
  }

  return json({ ok: true, id: data.id ?? null }, 200);
});

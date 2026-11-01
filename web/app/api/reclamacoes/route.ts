// Proxy da unica escrita publica. O navegador nunca fala direto com a API:
// isso mantem a API fora da internet e deixa um ponto so onde por limite de
// taxa e captcha depois, do lado de ca.
const BASE = process.env.API_BASE ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  let corpo: unknown;
  try {
    corpo = await req.json();
  } catch {
    return Response.json({ erro: "corpo inválido" }, { status: 400 });
  }
  const r = await fetch(`${BASE}/reclamacoes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
    cache: "no-store",
  });
  return Response.json(await r.json().catch(() => ({ erro: "falha" })),
                       { status: r.status });
}

// Proxy do roteamento: o formulario consulta no cliente a cada troca de tema.
const BASE = process.env.API_BASE ?? "http://127.0.0.1:8000";

export async function GET(req: Request) {
  const u = new URL(req.url);
  const tema = u.searchParams.get("tema") ?? "";
  const ente = u.searchParams.get("ente") ?? "";
  if (!tema || !/^\d{1,7}$/.test(ente)) {
    return Response.json({ erro: "parâmetros inválidos" }, { status: 400 });
  }
  const r = await fetch(
    `${BASE}/reclamacoes/rota?tema=${encodeURIComponent(tema)}&ente=${ente}`,
    { next: { revalidate: 600 } },
  );
  if (!r.ok) return Response.json({ erro: "falha" }, { status: r.status });
  return Response.json(await r.json());
}

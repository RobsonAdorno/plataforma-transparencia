// Proxy para o mapa consultar o municipio sem o navegador falar direto com a
// API. Mantem a API fora da internet e dispensa CORS - o componente do mapa e
// interativo e precisa buscar no clique, nao na renderizacao do servidor.
const BASE = process.env.API_BASE ?? "http://127.0.0.1:8000";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ ibge: string }> },
) {
  const { ibge } = await params;
  if (!/^\d{1,7}$/.test(ibge)) {
    return Response.json({ erro: "código inválido" }, { status: 400 });
  }
  const r = await fetch(`${BASE}/municipio/${ibge}`, {
    next: { revalidate: 900 },
  });
  if (!r.ok) {
    return Response.json({ erro: "município não encontrado" }, { status: r.status });
  }
  return Response.json(await r.json(), {
    headers: { "Cache-Control": "public, max-age=900" },
  });
}

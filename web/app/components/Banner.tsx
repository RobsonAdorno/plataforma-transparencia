import Link from "next/link";
import { dataHoraBr, type Panorama } from "../lib/api";

// O aviso do topo: tem alguma coisa sendo votada?
//
// O caso mais comum, e o que a maioria dos painéis esconde, é "não tem nada".
// Em ano eleitoral e em recesso o Congresso passa semanas parado, e um banner
// que inventa movimento nesse período treina a pessoa a ignorá-lo. Então o
// estado "nada" tem texto próprio e diz por quê.

const QUANDO: Record<Panorama["quando"], { selo: string; vivo: boolean }> = {
  agora:  { selo: "Acontecendo agora", vivo: true },
  hoje:   { selo: "Hoje no Congresso", vivo: true },
  amanha: { selo: "Amanhã no Congresso", vivo: false },
  depois: { selo: "Próxima sessão marcada", vivo: false },
  nada:   { selo: "Sem pauta marcada", vivo: false },
};

export default function Banner({ p }: { p: Panorama }) {
  const { selo, vivo } = QUANDO[p.quando];
  const lista = p.agora.length ? p.agora : p.proximas;
  const primeira = lista[0];

  if (p.quando === "nada" || !primeira) {
    return (
      <div className="banner">
        <span className="banner-selo">{selo}</span>
        <h2>Nenhuma votação marcada nos próximos dias</h2>
        <p className="muted" style={{ fontSize: 14, margin: "8px 0 0", maxWidth: "60ch" }}>
          Isso é o calendário do Congresso, não falta de dado. Em recesso e em
          ano eleitoral a agenda fica vazia por semanas seguidas.
        </p>
        <Link href="/leis/acervo" className="banner-mais">
          Ver todas as leis de 2026 →
        </Link>
      </div>
    );
  }

  // Requerimento nao e lei. Chamar um REQ de audiencia publica de "lei sendo
  // votada" no lugar mais visivel da tela seria o pior tipo de imprecisao.
  const nome = `${primeira.tipo} ${primeira.numero}/${primeira.ano}`;
  const titulo = primeira.vira_lei
    ? (p.quando === "agora"
        ? `${nome} está em votação agora`
        : `${nome} vai ser votada`)
    : (p.quando === "agora"
        ? `O Congresso está em sessão agora`
        : `Sessão marcada no Congresso`);

  return (
    <Link href="/leis/acervo" className="banner" data-vivo={vivo ? "" : undefined}>
      <span className="banner-selo">
        {vivo && <span className="pulso" aria-hidden />}
        {selo}
      </span>
      <h2>{titulo}</h2>
      {!primeira.vira_lei && (
        <p className="mono muted" style={{ fontSize: 11.5, margin: "6px 0 0" }}>
          a pauta do momento tem requerimentos, não projetos de lei — o que
          está em discussão é {nome}
        </p>
      )}
      <p className="muted" style={{ fontSize: 14, margin: "8px 0 0", maxWidth: "62ch" }}>
        {primeira.ementa?.slice(0, 180)}
        {(primeira.ementa?.length ?? 0) > 180 && "…"}
      </p>
      {lista.length > 1 && (
        <ul className="banner-lista">
          {lista.slice(1, 4).map((i) => (
            <li key={`${i.id}-${i.evento_id}`}>
              <span className="mono">{i.tipo} {i.numero}/{i.ano}</span>
              <span>{i.ementa?.slice(0, 90)}…</span>
            </li>
          ))}
        </ul>
      )}
      <span className="banner-mais">
        {p.quando === "agora"
          ? `em ${primeira.evento_tipo ?? "sessão"} · ver todas as leis de 2026 →`
          : `${dataHoraBr(primeira.inicio)} · ver todas as leis de 2026 →`}
      </span>
    </Link>
  );
}

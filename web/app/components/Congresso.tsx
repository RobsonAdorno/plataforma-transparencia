"use client";

import { useMemo, useState } from "react";
import Fonte from "./Fonte";
import type { CasaCongresso, Congresso as Dados } from "../lib/api";

/* O Congresso nas duas casas, com um interruptor entre elas.
 *
 * Vinte e um partidos em vinte e uma cores ninguem distingue - menos ainda
 * quem tem daltonismo. As cadeiras ficam neutras e so o partido escolhido
 * acende: fica mais legivel e serve melhor ao clique.
 *
 * O presidente da casa vem em destaque acima da bancada, e nao perdido numa
 * lista de Mesa, porque e ele quem decide o que entra em pauta. Projeto com
 * maioria e sem pauta nao vira lei, e essa e a parte do processo que menos
 * aparece. */

function assentos(n: number) {
  const fileiras = Math.max(4, Math.round(Math.sqrt(n / 3)));
  const r0 = 0.45, r1 = 1.0;
  const raios = Array.from({ length: fileiras },
    (_, i) => r0 + ((r1 - r0) * i) / (fileiras - 1));
  const soma = raios.reduce((a, b) => a + b, 0);
  const qtd = raios.map((r) => Math.max(1, Math.round((n * r) / soma)));
  let dif = n - qtd.reduce((a, b) => a + b, 0);
  let i = qtd.length - 1;
  while (dif !== 0) {
    qtd[i] += dif > 0 ? 1 : -1;
    dif += dif > 0 ? -1 : 1;
    i = (i - 1 + qtd.length) % qtd.length;
  }
  const pts: { x: number; y: number; a: number }[] = [];
  raios.forEach((r, ri) => {
    const c = qtd[ri];
    for (let k = 0; k < c; k++) {
      const t = c === 1 ? 0.5 : k / (c - 1);
      const a = Math.PI - t * Math.PI;
      pts.push({ x: Math.cos(a) * r, y: -Math.sin(a) * r, a });
    }
  });
  pts.sort((p, q) => q.a - p.a);
  const raio = Math.min(0.034, (Math.PI * r1 / qtd[qtd.length - 1]) * 0.36);
  return { pts, raio };
}

export default function Congresso({ dados }: { dados: Dados }) {
  const [casa, setCasa] = useState(0);
  const [sel, setSel] = useState<string | null>(null);
  const atual: CasaCongresso = dados.casas[casa] ?? dados.casas[0];

  const { pts, raio } = useMemo(() => assentos(atual.total), [atual.total]);
  const partidoPorAssento = useMemo(() => {
    const ordem: string[] = [];
    atual.partidos.forEach((p) => {
      for (let k = 0; k < p.cadeiras; k++) ordem.push(p.partido);
    });
    return ordem;
  }, [atual.partidos]);

  const maior = Math.max(1, ...atual.partidos.map((p) => p.cadeiras));
  const escolhido = atual.partidos.find((p) => p.partido === sel);
  const pres = atual.presidente;

  return (
    <div>
      {/* ------------------------------------------- quem preside a casa */}
      {pres && (
        <div className="faixa-presidente">
          {pres.foto_url && (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img src={pres.foto_url} alt="" width={52} height={52} />
          )}
          <div>
            <p className="mono rotulo-campo" style={{ margin: 0 }}>
              Preside {atual.nome}
              <Fonte chave={atual.casa === "senado" ? "senado_processo" : "camara_api"}
                     rotulo="Mesa Diretora" />
            </p>
            <p className="nome-pres">
              {pres.nome}
              {pres.partido && (
                <span className="local">{pres.partido}{pres.uf ? `-${pres.uf}` : ""}</span>
              )}
            </p>
            <p className="muted" style={{ fontSize: 13, margin: "4px 0 0", maxWidth: "58ch" }}>
              É quem decide o que entra na pauta. Um projeto pode ter maioria e
              nunca ser votado se o presidente da casa não o pautar.
            </p>
          </div>
          <div className="troca-casa" role="group" aria-label="Escolher a casa">
            {dados.casas.map((c, i) => (
              <button key={c.casa} aria-pressed={i === casa}
                      onClick={() => { setCasa(i); setSel(null); }}>
                {c.casa === "camara" ? "Câmara" : "Senado"}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ------------------------------------------------- o hemiciclo */}
      <div className="cartao" style={{ overflow: "hidden", marginTop: 14 }}>
        <div className="mapa-grade" style={{ display: "grid" }}>
          <div style={{ borderRight: "1px solid var(--line)", minWidth: 0, padding: 8 }}>
            <svg viewBox="-1.08 -1.1 2.16 1.2" role="img"
                 aria-label={`${atual.total} cadeiras do ${atual.nome} por partido`}
                 style={{ display: "block", width: "100%", height: "auto" }}>
              {pts.map((p, i) => {
                const dono = partidoPorAssento[i];
                const aceso = !sel || dono === sel;
                return (
                  <circle key={i} cx={p.x} cy={p.y} r={raio}
                    fill={sel && dono === sel ? "var(--accent)" : "var(--line)"}
                    fillOpacity={aceso ? 1 : 0.4}
                    style={{ transition: "fill .18s" }} />
                );
              })}
            </svg>
          </div>
          <div style={{ padding: "16px 15px", minWidth: 0 }}>
            <h3 style={{ fontFamily: "var(--fonte-titulo)", fontSize: 19, margin: 0 }}>
              {atual.nome}
            </h3>
            <p className="mono muted" style={{ fontSize: 11, letterSpacing: ".07em",
                 textTransform: "uppercase", margin: "3px 0 14px" }}>
              {escolhido
                ? `${escolhido.partido} · ${escolhido.cadeiras} de ${atual.total}`
                : `${atual.total} cadeiras · ${atual.partidos.length} partidos`}
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 1,
                          maxHeight: 320, overflowY: "auto" }}>
              {atual.partidos.map((p) => (
                <button key={p.partido} className="barra"
                  aria-pressed={sel === p.partido}
                  onClick={() => setSel(sel === p.partido ? null : p.partido)}>
                  <span className="bnome">{p.partido}</span>
                  <span className="btrilho">
                    <span className="bpreenche"
                          style={{ width: `${(p.cadeiras / maior) * 100}%` }} />
                  </span>
                  <span className="mono bnum">{p.cadeiras}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="legenda">
          clique num partido para acender as cadeiras dele
          <span style={{ marginLeft: "auto" }}>
            {atual.total === atual.cadeiras_por_lei
              ? `${atual.cadeiras_por_lei} cadeiras, casa completa`
              : `${atual.total} de ${atual.cadeiras_por_lei} cadeiras carregadas`}
          </span>
        </div>
      </div>

      {atual.mesa.length > 1 && (
        <details className="mesa-resto">
          <summary className="mono ver-mais">
            ver a Mesa Diretora inteira ({atual.mesa.length} cargos)
          </summary>
          <ul className="lista-reg">
            {atual.mesa.map((m) => (
              <li key={`${m.cargo}-${m.nome}`}
                  style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <p>{m.nome}<span className="lei-ref">{m.cargo}</span></p>
                <span className="mono muted" style={{ fontSize: 12, whiteSpace: "nowrap" }}>
                  {m.partido}{m.uf ? `-${m.uf}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

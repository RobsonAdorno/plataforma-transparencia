"use client";

import { useMemo, useState } from "react";
import type { Congresso } from "../lib/api";

/* Vinte e um partidos em vinte e uma cores ninguem distingue - menos ainda
   quem tem daltonismo. As cadeiras ficam neutras e so o partido selecionado
   acende. Fica mais legivel e serve melhor ao clique. */
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
  const raio = Math.min(0.03, (Math.PI * r1 / qtd[qtd.length - 1]) * 0.36);
  return { pts, raio };
}

export default function Hemiciclo({ dados }: { dados: Congresso }) {
  const [sel, setSel] = useState<string | null>(null);
  const { pts, raio } = useMemo(() => assentos(dados.total), [dados.total]);

  const partidoPorAssento = useMemo(() => {
    const ordem: string[] = [];
    dados.partidos.forEach((p) => {
      for (let k = 0; k < p.cadeiras; k++) ordem.push(p.partido);
    });
    return ordem;
  }, [dados.partidos]);

  const maior = Math.max(...dados.partidos.map((p) => p.cadeiras));
  const escolhido = dados.partidos.find((p) => p.partido === sel);

  return (
    <div className="cartao" style={{ overflow: "hidden" }}>
      <div className="mapa-grade" style={{ display: "grid" }}>
        <div style={{ borderRight: "1px solid var(--line)", minWidth: 0, padding: 8 }}>
          <svg viewBox="-1.08 -1.1 2.16 1.2" role="img"
               aria-label={`${dados.total} cadeiras por partido`}
               style={{ display: "block", width: "100%", height: "auto" }}>
            {pts.map((p, i) => {
              const dono = partidoPorAssento[i];
              const aceso = !sel || dono === sel;
              return (
                <circle key={i} cx={p.x} cy={p.y} r={raio}
                  fill={sel && dono === sel ? "var(--accent)" : "var(--line)"}
                  fillOpacity={aceso ? 1 : 0.45}
                  style={{ transition: "fill .18s" }} />
              );
            })}
          </svg>
        </div>
        <div style={{ padding: "16px 15px", minWidth: 0 }}>
          <h2 style={{ fontSize: 20 }}>{dados.casa}</h2>
          <p className="mono muted" style={{ fontSize: 11, letterSpacing: ".07em",
               textTransform: "uppercase", margin: "2px 0 14px" }}>
            {escolhido
              ? `${escolhido.partido} · ${escolhido.cadeiras} de ${dados.total}`
              : `${dados.total} cadeiras · ${dados.partidos.length} partidos`}
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 1,
                        maxHeight: 340, overflowY: "auto" }}>
            {dados.partidos.map((p) => (
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
        <span style={{ marginLeft: "auto" }}>legislatura em exercício</span>
      </div>
    </div>
  );
}

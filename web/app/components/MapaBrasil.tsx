"use client";

import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";
import malha from "../br-paths.json";
import type { Uf } from "../lib/api";
import { brl } from "../lib/api";

type Props = { ufs: Uf[] };

const caixa = (d: string) => {
  const re = /[ML](-?[\d.]+) (-?[\d.]+)/g;
  let m: RegExpExecArray | null, x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  while ((m = re.exec(d))) {
    const x = +m[1], y = +m[2];
    if (x < x0) x0 = x; if (x > x1) x1 = x;
    if (y < y0) y0 = y; if (y > y1) y1 = y;
  }
  return [x0, y0, x1 - x0, y1 - y0] as const;
};

export default function MapaBrasil({ ufs }: Props) {
  const router = useRouter();
  const svgRef = useRef<SVGSVGElement>(null);
  const [foco, setFoco] = useState<string | null>(null);
  const [dica, setDica] = useState<{ x: number; y: number; txt: string } | null>(null);

  const porUf = useMemo(() => Object.fromEntries(ufs.map((u) => [u.uf, u])), [ufs]);
  const paths = malha.paths as Record<string, string>;
  const siglas = useMemo(() => Object.keys(paths).sort(), [paths]);

  const max = Math.max(...ufs.map((u) => u.gasto_cota), 1);
  const min = Math.min(...ufs.map((u) => u.gasto_cota));

  const viewBox = useMemo(() => {
    if (!foco) return `0 0 ${malha.w} ${malha.h}`;
    const [x, y, w, h] = caixa(paths[foco]);
    const p = Math.max(w, h) * 0.12;
    return `${x - p} ${y - p} ${w + p * 2} ${h + p * 2}`;
  }, [foco, paths]);

  const total = ufs.reduce((s, u) => s + u.gasto_cota, 0);

  return (
    <div className="cartao" style={{ overflow: "hidden" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr" }} className="mapa-grade">
        <div style={{ position: "relative", borderRight: "1px solid var(--line)", minWidth: 0 }}>
          <svg
            ref={svgRef}
            viewBox={viewBox}
            role="img"
            aria-label="Mapa do Brasil por estado"
            style={{ display: "block", width: "100%", height: "auto",
                     transition: "all .5s cubic-bezier(.22,1,.36,1)" }}
          >
            {siglas.map((s) => {
              const u = porUf[s];
              const t = u ? (u.gasto_cota - min) / (max - min || 1) : 0;
              return (
                <path
                  key={s}
                  d={paths[s]}
                  fill="var(--accent)"
                  fillOpacity={0.14 + Math.pow(t, 0.6) * 0.86}
                  stroke="var(--surface)"
                  strokeWidth={2.2}
                  tabIndex={0}
                  role="button"
                  aria-label={u?.nome ?? s}
                  style={{ cursor: "pointer", opacity: foco && foco !== s ? 0.22 : 1,
                           transition: "opacity .25s" }}
                  onClick={() => setFoco(foco === s ? null : s)}
                  onDoubleClick={() => router.push(`/uf/${s.toLowerCase()}`)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") router.push(`/uf/${s.toLowerCase()}`);
                  }}
                  onMouseMove={(e) => {
                    const r = svgRef.current!.getBoundingClientRect();
                    setDica({ x: e.clientX - r.left, y: e.clientY - r.top,
                              txt: `${u?.nome ?? s} · ${u?.deputados ?? 0} deputados` });
                  }}
                  onMouseLeave={() => setDica(null)}
                />
              );
            })}
          </svg>
          {foco && (
            <button onClick={() => setFoco(null)} className="voltar">← Brasil</button>
          )}
          {dica && (
            <span className="dica" style={{ left: dica.x, top: dica.y }}>{dica.txt}</span>
          )}
        </div>

        <div style={{ padding: "18px 17px", minWidth: 0 }}>
          <h2 style={{ fontSize: 21 }}>{foco ? porUf[foco]?.nome : "Brasil"}</h2>
          <p className="mono muted" style={{ fontSize: 11, letterSpacing: ".07em",
               textTransform: "uppercase", margin: "2px 0 16px" }}>
            {foco ? "clique de novo para voltar" : "27 unidades federativas"}
          </p>

          {foco ? (
            <>
              <Linha rotulo="Deputados federais" valor={String(porUf[foco]?.deputados ?? 0)} />
              <Linha rotulo="Cota parlamentar em 2026" valor={brl(porUf[foco]?.gasto_cota ?? 0)} />
              <a className="selo" style={{ marginTop: 16, display: "inline-block" }}
                 href={`/uf/${foco.toLowerCase()}`}>Ver a bancada →</a>
            </>
          ) : (
            <>
              <Linha rotulo="Deputados federais" valor="513" />
              <Linha rotulo="Senadores" valor="81" />
              <Linha rotulo="Cota parlamentar em 2026" valor={brl(total)} />
              <p className="muted" style={{ fontSize: 13, marginTop: 16 }}>
                Clique num estado para focar, duas vezes ou Enter para abrir a bancada.
              </p>
            </>
          )}
        </div>
      </div>
      <div className="legenda">
        <span>menos gasto</span>
        {[0.16, 0.34, 0.55, 0.78, 1].map((o) => (
          <i key={o} style={{ width: 15, height: 11, borderRadius: 2,
               background: "var(--accent)", opacity: o, display: "inline-block" }} />
        ))}
        <span>mais gasto</span>
        <span style={{ marginLeft: "auto" }}>cota parlamentar · Câmara dos Deputados</span>
      </div>
    </div>
  );
}

function Linha({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline",
                  gap: 12, padding: "8px 0", borderBottom: "1px dotted var(--line)" }}>
      <span style={{ fontSize: 13.5, color: "var(--muted)" }}>{rotulo}</span>
      <b className="mono" style={{ fontSize: 16 }}>{valor}</b>
    </div>
  );
}

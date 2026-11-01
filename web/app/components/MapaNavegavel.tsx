"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import malhaBr from "../br-paths.json";
import type { Uf } from "../lib/api";

// Tres niveis num componente so, porque o usuario quer uma aba de mapa e nao
// tres paginas: Brasil -> estado -> municipio. A malha de municipios de cada
// estado e um arquivo separado em /malhas/{UF}.json, buscado no clique: sao
// 91 KB em media e 296 KB no pior caso (Minas, com 853 municipios). Carregar
// os 27 de uma vez seriam 2,5 MB para ver um estado.

type Municipio = { c: string; n: string; d: string; x: number; y: number };
type Malha = { uf: string; w: number; h: number; municipios: Municipio[] };

type Detalhe = {
  codigo_ibge: string; nome: string; uf: string; populacao: number | null;
  prefeito: { nome_urna: string; partido: string | null } | null;
  vereadores: { id: number; nome_urna: string; partido: string | null }[];
  cobertura: Record<string, {
    situacao: "publicado" | "nao_publicado" | "nao_se_aplica";
    candidaturas: number; sem_resultado: number; motivo: string | null;
  }>;
  faixa_censo: { letra: string; max_vereadores: number } | null;
  faixa_referencia: { letra: string; max_vereadores: number } | null;
};

// O JSON importado tipa os pares como number[], nao como tupla: Record de
// number[] e o tipo honesto aqui.
const rotulos: Record<string, number[]> = malhaBr.rotulos;
const guias: Record<string, number[]> = malhaBr.guias ?? {};

const BRL = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL",
                              maximumFractionDigits: 0 });

export default function MapaNavegavel({ ufs }: { ufs: Uf[] }) {
  const [uf, setUf] = useState<string | null>(null);
  const [malha, setMalha] = useState<Malha | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erroMalha, setErroMalha] = useState<string | null>(null);
  const [mun, setMun] = useState<string | null>(null);
  const [detalhe, setDetalhe] = useState<Detalhe | null>(null);
  const [buscandoMun, setBuscandoMun] = useState(false);
  const [busca, setBusca] = useState("");
  const [hover, setHover] = useState<string | null>(null);
  const cache = useRef<Map<string, Malha>>(new Map());

  const porUf = useMemo(
    () => new Map(ufs.map((u) => [u.uf, u])), [ufs]);

  const abreEstado = useCallback(async (sigla: string) => {
    setUf(sigla); setMun(null); setDetalhe(null); setBusca("");
    setErroMalha(null);
    const guardada = cache.current.get(sigla);
    if (guardada) { setMalha(guardada); return; }
    setCarregando(true);
    try {
      const r = await fetch(`/malhas/${sigla}.json`);
      if (!r.ok) throw new Error(String(r.status));
      const m: Malha = await r.json();
      cache.current.set(sigla, m);
      setMalha(m);
    } catch {
      setErroMalha("Não foi possível carregar o mapa deste estado. "
                   + "A lista de municípios abaixo continua funcionando.");
      setMalha(null);
    } finally {
      setCarregando(false);
    }
  }, []);

  const abreMunicipio = useCallback(async (codigo: string) => {
    setMun(codigo); setDetalhe(null); setBuscandoMun(true);
    try {
      const r = await fetch(`/api/municipio/${codigo}`);
      setDetalhe(r.ok ? await r.json() : null);
    } catch {
      setDetalhe(null);
    } finally {
      setBuscandoMun(false);
    }
  }, []);

  // Esc sobe um nivel. Teclado importa num mapa: clicar em municipio pequeno
  // e dificil, e quem errou precisa de uma saida obvia.
  useEffect(() => {
    const sair = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (mun) { setMun(null); setDetalhe(null); }
      else if (uf) { setUf(null); setMalha(null); }
    };
    window.addEventListener("keydown", sair);
    return () => window.removeEventListener("keydown", sair);
  }, [uf, mun]);

  const filtrados = useMemo(() => {
    if (!malha) return [];
    const q = busca.trim().toLowerCase();
    if (!q) return malha.municipios;
    return malha.municipios.filter((m) => m.n.toLowerCase().includes(q));
  }, [malha, busca]);

  // ------------------------------------------------------------- nível 1
  if (!uf) {
    const totalVer = ufs.reduce((a, u) => a + u.vereadores, 0);
    const totalMun = ufs.reduce((a, u) => a + u.municipios, 0);
    return (
      <div>
        <div className="cartao" style={{ position: "relative", overflow: "hidden" }}>
          <svg viewBox={`0 0 ${malhaBr.w} ${malhaBr.h}`} className="mapa-svg"
               role="group" aria-label="Mapa do Brasil por estado">
            {Object.entries(malhaBr.paths).map(([sigla, d]) => {
              const u = porUf.get(sigla);
              return (
                <path key={sigla} d={d as string} className="uf"
                      data-hover={hover === sigla ? "" : undefined}
                      tabIndex={0} role="button"
                      aria-label={`${u?.nome ?? sigla}: ${u?.vereadores ?? 0} vereadores`}
                      onMouseEnter={() => setHover(sigla)}
                      onMouseLeave={() => setHover(null)}
                      onFocus={() => setHover(sigla)}
                      onClick={() => abreEstado(sigla)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault(); abreEstado(sigla);
                        }
                      }} />
              );
            })}
            {/* Linhas-guia dos estados pequenos, antes dos rotulos para
                ficarem por baixo. Oito estados nao tem espaco interno para a
                sigla: ela sai para a margem e a linha liga os dois. */}
            {Object.entries(guias).map(([sigla, a]) => {
              const r = rotulos[sigla];
              return (
                <line key={`g${sigla}`} x1={a[0]} y1={a[1]}
                      x2={r[0] - 16} y2={r[1] - 4} className="guia-uf" />
              );
            })}
            {Object.keys(malhaBr.paths).map((sigla) => {
              const r = rotulos[sigla];
              if (!r) return null;
              return (
                <text key={sigla} x={r[0]} y={r[1]} className="rotulo-uf"
                      data-fora={guias[sigla] ? "" : undefined}
                      data-hover={hover === sigla ? "" : undefined}
                      onMouseEnter={() => setHover(sigla)}
                      onMouseLeave={() => setHover(null)}
                      onClick={() => abreEstado(sigla)}>
                  {sigla}
                </text>
              );
            })}
          </svg>
          {hover && porUf.get(hover) && (
            <div className="painel-flutuante">
              <strong>{porUf.get(hover)!.nome}</strong>
              <div className="mono">
                {porUf.get(hover)!.municipios} municípios ·{" "}
                {porUf.get(hover)!.vereadores.toLocaleString("pt-BR")} vereadores
              </div>
            </div>
          )}
        </div>
        <p className="muted" style={{ fontSize: 13.5, marginTop: 12 }}>
          {totalMun.toLocaleString("pt-BR")} municípios e{" "}
          {totalVer.toLocaleString("pt-BR")} vereadores. Clique num estado para
          ver as cidades dele.
        </p>
      </div>
    );
  }

  const u = porUf.get(uf);

  // ------------------------------------------------------------- nível 2 e 3
  return (
    <div>
      <div className="trilha-mapa">
        <button onClick={() => { setUf(null); setMalha(null); setMun(null); setDetalhe(null); }}>
          Brasil
        </button>
        <span>›</span>
        {mun ? (
          <>
            <button onClick={() => { setMun(null); setDetalhe(null); }}>
              {u?.nome ?? uf}
            </button>
            <span>›</span>
            <strong>{detalhe?.nome ?? malha?.municipios.find((m) => m.c === mun)?.n}</strong>
          </>
        ) : (
          <strong>{u?.nome ?? uf}</strong>
        )}
        <span className="mono dica-esc">esc volta</span>
      </div>

      <div className="grade mapa-grade">
        <div className="cartao" style={{ position: "relative", overflow: "hidden" }}>
          {carregando && <p className="vazio-mapa">carregando o mapa de {uf}…</p>}
          {erroMalha && <p className="vazio-mapa">{erroMalha}</p>}
          {malha && (
            <svg viewBox={`0 0 ${malha.w} ${malha.h}`} className="mapa-svg"
                 role="group" aria-label={`Municípios de ${u?.nome ?? uf}`}>
              {malha.municipios.map((m) => {
                const visivel = !busca || filtrados.includes(m);
                return (
                  <path key={m.c} d={m.d} className="mun"
                        data-sel={mun === m.c ? "" : undefined}
                        data-apagado={!visivel ? "" : undefined}
                        tabIndex={visivel ? 0 : -1} role="button"
                        aria-label={m.n}
                        onMouseEnter={() => setHover(m.c)}
                        onMouseLeave={() => setHover(null)}
                        onFocus={() => setHover(m.c)}
                        onClick={() => abreMunicipio(m.c)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault(); abreMunicipio(m.c);
                          }
                        }} />
                );
              })}
              {/* Nome so do municipio sob o cursor ou selecionado: 853 rotulos
                  simultaneos em Minas nao seriam legiveis em tela nenhuma. */}
              {malha.municipios
                .filter((m) => m.c === hover || m.c === mun)
                .map((m) => (
                  <text key={`t${m.c}`} x={m.x} y={m.y} className="rotulo-mun">
                    {m.n}
                  </text>
                ))}
            </svg>
          )}
        </div>

        <div>
          {!mun ? (
            <div className="cartao" style={{ padding: 15 }}>
              <label className="mono rotulo-campo" htmlFor="busca-mun">
                Buscar cidade em {u?.nome ?? uf}
              </label>
              <input id="busca-mun" value={busca} autoComplete="off"
                     onChange={(e) => setBusca(e.target.value)}
                     placeholder="digite o nome" className="campo" />
              <p className="muted" style={{ fontSize: 12.5, margin: "8px 0 10px" }}>
                {filtrados.length.toLocaleString("pt-BR")} de{" "}
                {malha?.municipios.length ?? 0} cidades
              </p>
              <ul className="lista-mun">
                {filtrados.slice(0, 60).map((m) => (
                  <li key={m.c}>
                    <button onMouseEnter={() => setHover(m.c)}
                            onMouseLeave={() => setHover(null)}
                            onClick={() => abreMunicipio(m.c)}>
                      {m.n}
                    </button>
                  </li>
                ))}
              </ul>
              {filtrados.length > 60 && (
                <p className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>
                  Mostrando as 60 primeiras. Refine a busca.
                </p>
              )}
            </div>
          ) : (
            <PainelMunicipio detalhe={detalhe} carregando={buscandoMun}
                             nome={malha?.municipios.find((m) => m.c === mun)?.n ?? ""}
                             codigo={mun} />
          )}
        </div>
      </div>
    </div>
  );
}

/** O painel do municipio. Quando nao ha dado, DIZ que nao ha - e diz por que,
 *  separando "a cidade nao elege vereador" de "o TSE nao publicou". Mostrar
 *  zero sem explicacao seria afirmar algo falso sobre a cidade. */
function PainelMunicipio(
  { detalhe, carregando, nome, codigo }:
  { detalhe: Detalhe | null; carregando: boolean; nome: string; codigo: string },
) {
  if (carregando) {
    return <div className="cartao" style={{ padding: 15 }}>
      <p className="muted">carregando {nome}…</p></div>;
  }
  if (!detalhe) {
    return (
      <div className="cartao" style={{ padding: 15 }}>
        <h3 style={{ fontFamily: "var(--fonte-titulo)", fontSize: 17 }}>{nome}</h3>
        <p className="aviso" style={{ marginTop: 10 }}>
          <strong>Não temos informações sobre esta prefeitura.</strong> O código
          IBGE {codigo} não retornou dados. Se a cidade foi criada
          recentemente, pode ainda não constar das bases oficiais que usamos.
        </p>
      </div>
    );
  }

  const cv = detalhe.cobertura?.["VEREADOR"];
  const cp = detalhe.cobertura?.["PREFEITO"];
  const teto = Math.max(detalhe.faixa_censo?.max_vereadores ?? 0,
                        detalhe.faixa_referencia?.max_vereadores ?? 0);
  const porPartido = new Map<string, number>();
  for (const v of detalhe.vereadores) {
    const p = v.partido ?? "sem partido";
    porPartido.set(p, (porPartido.get(p) ?? 0) + 1);
  }

  return (
    <div className="cartao" style={{ padding: 15 }}>
      <h3 style={{ fontFamily: "var(--fonte-titulo)", fontSize: 18, margin: 0 }}>
        {detalhe.nome}
      </h3>
      <p className="mono muted" style={{ fontSize: 11.5, margin: "3px 0 12px" }}>
        {detalhe.uf}
        {detalhe.populacao && ` · ${detalhe.populacao.toLocaleString("pt-BR")} habitantes`}
      </p>

      <h4 className="rotulo-campo mono">Prefeito</h4>
      {detalhe.prefeito ? (
        <p style={{ margin: "4px 0 0", fontSize: 15.5 }}>
          {detalhe.prefeito.nome_urna}
          {detalhe.prefeito.partido && <span className="local">{detalhe.prefeito.partido}</span>}
        </p>
      ) : (
        <p className="aviso" style={{ marginTop: 6, fontSize: 13 }}>
          <strong>Não temos informações sobre esta prefeitura.</strong>{" "}
          {cp?.motivo ?? "O resultado não consta das bases que usamos."}
        </p>
      )}

      <h4 className="rotulo-campo mono" style={{ marginTop: 16 }}>
        Câmara Municipal
      </h4>
      {detalhe.vereadores.length > 0 ? (
        <>
          <p className="mono" style={{ fontSize: 13, margin: "4px 0 8px" }}>
            {detalhe.vereadores.length} vereadores
            {teto > 0 && <span className="muted"> · teto da Constituição: {teto}</span>}
          </p>
          <div className="chips">
            {[...porPartido.entries()].sort((a, b) => b[1] - a[1]).map(([p, n]) => (
              <span key={p} className="chip">{p} {n}</span>
            ))}
          </div>
          <details style={{ marginTop: 10 }}>
            <summary className="mono ver-mais">ver os {detalhe.vereadores.length} nomes</summary>
            <ul className="lista-nomes">
              {detalhe.vereadores.map((v) => (
                <li key={v.id}>{v.nome_urna}
                  <span className="muted"> {v.partido ?? ""}</span></li>
              ))}
            </ul>
          </details>
        </>
      ) : (
        <p className="aviso" style={{ marginTop: 6, fontSize: 13 }}>
          <strong>
            {cv?.situacao === "nao_se_aplica"
              ? "Esta cidade não elege vereadores."
              : "Não temos informações sobre esta câmara."}
          </strong>{" "}
          {cv?.motivo ?? "O resultado não consta das bases que usamos."}
        </p>
      )}

      <h4 className="rotulo-campo mono" style={{ marginTop: 16 }}>
        Gastos e leis do município
      </h4>
      <p className="aviso" style={{ marginTop: 6, fontSize: 13 }}>
        <strong>Não temos informações sobre esta prefeitura.</strong> Gasto de
        gabinete e projeto de lei municipal não têm fonte padronizada: são 5.571
        câmaras, sem API e sem arquivo aberto. Entram aqui por importação
        revisada, cidade por cidade.{" "}
        <Link href="/cobertura">Por que isso falta →</Link>
      </p>

      <div className="acoes-painel">
        <Link href={`/municipio/${detalhe.codigo_ibge}`} className="botao">
          Página completa da cidade
        </Link>
        <Link href={`/reclamar?ente=${detalhe.codigo_ibge}`} className="botao b-sec">
          Abrir reclamação
        </Link>
      </div>
    </div>
  );
}

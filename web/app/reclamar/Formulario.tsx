"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Passo, Rota, TemaCompetencia } from "../lib/api";

// O ponto do formulario nao e coletar texto: e DESCOBRIR de quem e o problema
// enquanto a pessoa escreve. Por isso o painel de roteamento aparece no
// momento em que o tema e escolhido, antes de qualquer envio - e o instante em
// que a informacao ensina. Quem reclama de poste descobre ali que poste e da
// prefeitura e energia e da concessionaria, e para de cobrar do deputado.

type Cidade = { codigo_ibge: string; nome: string; uf: string };

export default function Formulario(
  { temas, cidade }: { temas: TemaCompetencia[]; cidade: Cidade | null },
) {
  const [tema, setTema] = useState("");
  const [titulo, setTitulo] = useState("");
  const [descricao, setDescricao] = useState("");
  const [local, setLocal] = useState("");
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [exibir, setExibir] = useState(false);
  const [rota, setRota] = useState<Rota | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [pronto, setPronto] = useState<{ protocolo: string; encaminhavel: boolean } | null>(null);

  const porEsfera = useMemo(() => {
    const m = new Map<string, TemaCompetencia[]>();
    for (const t of temas) {
      m.set(t.esfera, [...(m.get(t.esfera) ?? []), t]);
    }
    return m;
  }, [temas]);

  useEffect(() => {
    if (!tema || !cidade) { setRota(null); return; }
    let vivo = true;
    fetch(`/api/rota?tema=${encodeURIComponent(tema)}&ente=${cidade.codigo_ibge}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (vivo) setRota(d); })
      .catch(() => { if (vivo) setRota(null); });
    return () => { vivo = false; };
  }, [tema, cidade]);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!cidade) return;
    setEnviando(true); setErro(null);
    try {
      const r = await fetch("/api/reclamacoes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ente_codigo: cidade.codigo_ibge, tema, titulo, descricao,
          local_referencia: local || null,
          autor_nome: nome || null, autor_email: email || null,
          exibir_autor: exibir,
        }),
      });
      const d = await r.json();
      if (!r.ok) {
        setErro(r.status === 429
          ? "Você já abriu várias reclamações na última hora. Tente mais tarde."
          : (typeof d?.detail === "string" ? d.detail
             : "Confira os campos: o título precisa de 6 caracteres e a "
               + "descrição de 20."));
        return;
      }
      setPronto({ protocolo: d.protocolo, encaminhavel: d.encaminhavel });
    } catch {
      setErro("Não foi possível enviar agora. Tente de novo em alguns minutos.");
    } finally {
      setEnviando(false);
    }
  }

  if (!cidade) {
    return (
      <p className="aviso" style={{ marginTop: 20 }}>
        <strong>Escolha a cidade primeiro.</strong> Abra o{" "}
        <Link href="/">mapa</Link>, desça até o seu município e use o botão
        “Abrir reclamação” — é assim que a plataforma sabe para qual prefeitura
        rotear.
      </p>
    );
  }

  if (pronto) {
    return (
      <div className="cartao" style={{ padding: 20, marginTop: 20 }}>
        <span className="selo">Registrada</span>
        <h2 style={{ fontSize: 21, margin: "10px 0 0" }}>
          Protocolo {pronto.protocolo}
        </h2>
        <p className="muted" style={{ margin: "8px 0 0", maxWidth: "58ch" }}>
          Anote esse código: é por ele que você e qualquer pessoa acompanham a
          reclamação. Ela é pública desde já.
        </p>
        {!pronto.encaminhavel && (
          <p className="aviso" style={{ marginTop: 14 }}>
            <strong>Ainda não temos o canal oficial desta prefeitura cadastrado,</strong>{" "}
            então não há para onde encaminhar automaticamente. A reclamação fica
            registrada e pública, e a página dela traz o passo a passo para você
            protocolar na ouvidoria — o que também faz o prazo legal começar a
            correr.
          </p>
        )}
        <div className="acoes-painel">
          <Link href={`/reclamacao/${pronto.protocolo}`} className="botao">
            Acompanhar esta reclamação
          </Link>
          <Link href="/reclamacoes" className="botao b-sec">Ver todas</Link>
        </div>
      </div>
    );
  }

  const principal = rota?.responsaveis?.[0];

  return (
    <form onSubmit={enviar} style={{ marginTop: 22 }}>
      <div className="duas">
        <div className="cartao" style={{ padding: 16 }}>
          <p className="mono rotulo-campo">Cidade</p>
          <p style={{ margin: "0 0 16px", fontSize: 15.5 }}>
            {cidade.nome}, {cidade.uf}{" "}
            <Link href="/" className="mono" style={{ fontSize: 11 }}>trocar</Link>
          </p>

          <label className="mono rotulo-campo" htmlFor="tema">
            Qual é o problema
          </label>
          <select id="tema" className="campo" value={tema} required
                  onChange={(e) => setTema(e.target.value)}>
            <option value="">escolha o tema</option>
            {["MUNICIPAL", "ESTADUAL", "FEDERAL"].map((esf) => (
              <optgroup key={esf} label={
                esf === "MUNICIPAL" ? "Costuma ser da prefeitura"
                : esf === "ESTADUAL" ? "Costuma ser do estado"
                : "Costuma ser federal"}>
                {(porEsfera.get(esf) ?? []).map((t) => (
                  <option key={`${t.tema}-${t.esfera}`} value={t.tema}>{t.tema}</option>
                ))}
              </optgroup>
            ))}
          </select>

          <label className="mono rotulo-campo" htmlFor="titulo"
                 style={{ marginTop: 14 }}>
            Resuma em uma linha
          </label>
          <input id="titulo" className="campo" value={titulo} required
                 minLength={6} maxLength={140} autoComplete="off"
                 placeholder="Poste apagado há três semanas na Rua X"
                 onChange={(e) => setTitulo(e.target.value)} />

          <label className="mono rotulo-campo" htmlFor="descricao"
                 style={{ marginTop: 14 }}>
            Descreva o que está acontecendo
          </label>
          <textarea id="descricao" className="campo" value={descricao} required
                    minLength={20} maxLength={4000} rows={6}
                    placeholder="Desde quando, onde exatamente, e o que isso causa. Quanto mais concreto, mais difícil de ignorar."
                    onChange={(e) => setDescricao(e.target.value)} />
          <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>
            {descricao.length}/4000
          </p>

          <label className="mono rotulo-campo" htmlFor="local"
                 style={{ marginTop: 14 }}>
            Endereço ou referência (opcional)
          </label>
          <input id="local" className="campo" value={local} maxLength={200}
                 autoComplete="off" placeholder="Rua, número, bairro"
                 onChange={(e) => setLocal(e.target.value)} />

          <fieldset className="campo-grupo">
            <legend className="mono rotulo-campo">
              Seus dados (opcional)
            </legend>
            <p className="muted" style={{ fontSize: 12.5, margin: "0 0 10px" }}>
              Dá para reclamar sem se identificar. Se deixar e-mail, avisamos
              quando houver resposta ou quando o prazo vencer. O e-mail nunca
              aparece na página e fica guardado só como código embaralhado.
            </p>
            <input className="campo" value={nome} maxLength={120}
                   placeholder="nome" autoComplete="name"
                   onChange={(e) => setNome(e.target.value)} />
            <input className="campo" type="email" value={email} maxLength={160}
                   placeholder="e-mail" autoComplete="email"
                   style={{ marginTop: 8 }}
                   onChange={(e) => setEmail(e.target.value)} />
            <label className="marcar">
              <input type="checkbox" checked={exibir}
                     onChange={(e) => setExibir(e.target.checked)} />
              Mostrar meu nome na página pública
            </label>
          </fieldset>

          {erro && <p className="aviso" style={{ marginTop: 14 }}>{erro}</p>}

          <button type="submit" className="botao" disabled={enviando}
                  style={{ marginTop: 16, border: 0, cursor: "pointer" }}>
            {enviando ? "registrando…" : "Registrar reclamação pública"}
          </button>
        </div>

        {/* ------------------------------------------- de quem é o problema */}
        <div>
          {!tema ? (
            <div className="cartao" style={{ padding: 16 }}>
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>
                Escolha o tema e esta coluna mostra de quem é a
                responsabilidade, quem ocupa o cargo hoje na sua cidade, e o que
                fazer se não responderem.
              </p>
            </div>
          ) : rota?.indefinido ? (
            <p className="aviso">
              Ainda não classificamos esse tema. A reclamação é registrada do
              mesmo jeito, mas sem roteamento automático.
            </p>
          ) : (
            <>
              <div className="cartao" style={{ padding: 16 }}>
                <p className="mono rotulo-campo">
                  {rota && rota.responsaveis.length > 1
                    ? "Responsabilidade compartilhada"
                    : "De quem é"}
                </p>
                {rota?.responsaveis.map((r) => (
                  <div key={`${r.esfera}-${r.cargo_responsavel}`}
                       style={{ marginBottom: 14 }}>
                    <p style={{ margin: 0, fontSize: 15.5 }}>
                      <strong>
                        {r.esfera === "MUNICIPAL" ? "Prefeitura"
                         : r.esfera === "ESTADUAL" ? "Governo do estado"
                         : "Governo federal"}
                      </strong>
                      {r.ocupante && <> — {r.ocupante.nome_urna}
                        {r.ocupante.partido && (
                          <span className="local">{r.ocupante.partido}</span>)}</>}
                    </p>
                    {r.descricao && (
                      <p className="muted" style={{ fontSize: 13.5, margin: "5px 0 0" }}>
                        {r.descricao}
                      </p>
                    )}
                    <span className="lei-ref">{r.base_legal}</span>
                  </div>
                ))}
                {rota && rota.responsaveis.length > 1 && (
                  <p className="muted" style={{ fontSize: 13, margin: "4px 0 0" }}>
                    Esse tema é competência comum: mais de uma esfera responde,
                    e os dois endereços estão certos.
                  </p>
                )}
                {principal && (
                  <Link href={`/cargo/${principal.cargo_responsavel.toLowerCase()}`}
                        className="mono" style={{ fontSize: 11.5 }}>
                    O que esse cargo pode e não pode fazer →
                  </Link>
                )}
              </div>

              {rota?.escalonamento && rota.escalonamento.length > 0 && (
                <Escalonamento passos={rota.escalonamento} compacto />
              )}
            </>
          )}
        </div>
      </div>
    </form>
  );
}

export function Escalonamento(
  { passos, compacto }: { passos: Passo[]; compacto?: boolean },
) {
  return (
    <div className="cartao" style={{ marginTop: 14 }}>
      <div className="cabeca-pode" data-tipo="nao">
        Se não responderem no prazo
      </div>
      <ol className="escada">
        {passos.map((p) => (
          <li key={p.ordem}>
            <strong>{p.orgao}</strong>
            {!compacto && <p>{p.o_que_fazer}</p>}
            {compacto && <p className="curto">{p.o_que_fazer}</p>}
            {p.prazo && <span className="prazo mono">prazo: {p.prazo}</span>}
            {p.quando_usar && !compacto && (
              <p className="quando"><em>Quando usar:</em> {p.quando_usar}</p>
            )}
            <span className="lei-ref">{p.base_legal}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

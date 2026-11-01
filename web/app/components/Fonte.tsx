"use client";

import { useEffect, useId, useRef, useState } from "react";
import { FONTES, type ChaveFonte, type Fonte as Ficha } from "../lib/fontes";

// O ⓘ ao lado de cada número.
//
// A ideia é do usuário e é a coisa mais alinhada com o projeto que apareceu
// até agora: todo dado exibido precisa dizer o que é, de onde veio e ter um
// link para quem quiser bater. Sem isso a plataforma pede confiança; com isso
// ela permite conferência, que é diferente.
//
// Três decisões:
//
//  - abre no clique, não no hover. Hover não existe em telefone, e a pessoa
//    que mais precisa desta informação é a que está desconfiada — ela vai
//    clicar;
//  - cada ficha traz uma RESSALVA, quando existe. Dizer de onde veio o número
//    sem dizer o que ele não cobre é meia verdade: "58.174 vereadores" sem
//    "são os eleitos, não quem está no cargo hoje" induz a erro;
//  - o link vai para a página da fonte, não para o arquivo bruto de 200 MB.

export default function Fonte(
  { chave, rotulo }: { chave: ChaveFonte; rotulo?: string },
) {
  // Tipado como Ficha: o `as const` do registro estreita cada entrada ao
  // seu formato literal e some com os campos opcionais.
  const f: Ficha = FONTES[chave];
  const [aberto, setAberto] = useState(false);
  const caixa = useRef<HTMLSpanElement>(null);
  const id = useId();

  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => {
      if (caixa.current && !caixa.current.contains(e.target as Node)) {
        setAberto(false);
      }
    };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setAberto(false); };
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
  }, [aberto]);

  return (
    <span className="fonte" ref={caixa}>
      <button type="button" className="fonte-i" aria-expanded={aberto}
              aria-controls={id}
              aria-label={`De onde vem: ${rotulo ?? f.o_que.slice(0, 60)}`}
              onClick={(e) => { e.preventDefault(); e.stopPropagation();
                                setAberto((v) => !v); }}>
        i
      </button>
      {aberto && (
        <span className="fonte-ficha" id={id} role="dialog">
          <span className="fonte-oque">{f.o_que}</span>
          <span className="fonte-orgao">{f.orgao}</span>
          {f.ressalva && (
            <span className="fonte-ressalva">
              <strong>O que este dado não diz:</strong> {f.ressalva}
            </span>
          )}
          <a href={f.url} target="_blank" rel="noopener noreferrer">
            Conferir na fonte ↗
          </a>
          {f.quando && <span className="fonte-quando">{f.quando}</span>}
        </span>
      )}
    </span>
  );
}

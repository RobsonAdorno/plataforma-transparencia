// A barra de sete degraus: apresentado -> comissoes -> plenario -> casa
// revisora -> plenario revisor -> sancao -> lei. Desenhar o caminho inteiro,
// e nao so o ponto onde o projeto esta, e o que ensina: a pessoa ve quanta
// coisa ainda falta, e por que a maioria dos projetos nunca chega ao fim.
export default function Caminho({ fase, morto }: { fase: number | null; morto?: boolean }) {
  return (
    <div className="caminho" data-morto={morto ? "" : undefined}
         role="img" aria-label={`Etapa ${fase ?? 0} de 7 até virar lei`}>
      {[1, 2, 3, 4, 5, 6, 7].map((n) => (
        <span key={n} data-feito={fase !== null && n <= fase ? "" : undefined} />
      ))}
    </div>
  );
}

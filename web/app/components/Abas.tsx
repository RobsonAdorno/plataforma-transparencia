import Link from "next/link";

const ABAS = [
  ["/leis", "Panorama"],
  ["/leis/acervo", "Todas as leis"],
  ["/leis/agenda", "Vão ser votadas"],
  ["/leis/agora", "Sendo votadas"],
  ["/leis/votadas", "Já votadas"],
  ["/leis/normas", "Viraram lei"],
] as const;

export default function Abas({ atual }: { atual: string }) {
  return (
    <nav className="abas">
      {ABAS.map(([href, rotulo]) => (
        <Link key={href} href={href} aria-current={href === atual ? "page" : undefined}>
          {rotulo}
        </Link>
      ))}
    </nav>
  );
}

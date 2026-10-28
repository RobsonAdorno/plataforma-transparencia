# Plataforma de Transparência Política

Dados de quem foi eleito no Brasil, quanto gasta, como vota e para onde vai o
dinheiro público — a partir das fontes oficiais.

Arquitetura e decisões: https://claude.ai/artifact/CqwwuhRpr44FmD6G8MhBoC

## Estado atual — Fases 0 a 3

Pipeline completo, carregando em PostgreSQL:

| | |
|---|---|
| Pessoas | 567 (513 em exercício + 54 suplentes e ex-deputados que votaram) |
| Despesas de cota | 115.032 |
| Votações de 2026 | 7.436 — 155 nominais, 7.281 simbólicas |
| Votos individuais | 53.126, nenhum descartado |
| Proposições | 5.887, 100% das votações com matéria vinculada |
| Agenda | 78 eventos, 403 itens de pauta |
| Alertas | 78 rascunhos a partir de 10 meses — cerca de 2 por semana |
| Entes | 1 união, 27 estados, 5.571 municípios |
| Eleitos municipais | 58.174 vereadores e 5.568 prefeitos (TSE 2024) |

**513 de 513 deputados ligados ao TSE**, sendo 511 por CPF e 2 por nome dentro
da mesma UF. Fila de revisão vazia.

Além disso: API de leitura em FastAPI (`src/plataforma/api.py`), painel de
administração e front em Next.js (`web/`).

## Como rodar

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env          # defina CPF_SALT

export PYTHONPATH=src
./.venv/bin/python -m plataforma.cli ingest-camara --ano 2026
./.venv/bin/python -m plataforma.cli ingest-tse    --ano 2022
./.venv/bin/python -m plataforma.cli resolve       --ano 2022
```

Os brutos caem em `data/bronze/<fonte>/<data>/`, cada um com `.manifest.json`
contendo URL, hash e horário da coleta. O derivado vai em `data/derivado/`.
Nada disso entra no git.

## Decisões que o código carrega

**CPF nunca em claro no banco.** `config.hash_cpf` gera a chave de junção com
sal. O número cru fica só no bronze. O sal **não pode mudar** depois do primeiro
carregamento — trocar invalida todas as ligações já gravadas.

**A ponte entre TSE e Câmara.** O CSV da cota parlamentar é o único arquivo
oficial onde o CPF e o `ideCadastro` (id da API) aparecem na mesma linha:

```
TSE NR_CPF_CANDIDATO → CEAP cpf → CEAP ideCadastro → Câmara API id
```

**Nada entra no banco por palpite.** Acima de 0,93 de similaridade o vínculo é
automático; entre 0,80 e 0,93 vai para a fila com sugestão; abaixo disso vai
para a fila sem sugestão. Um merge errado atribui o gasto de um deputado a
outro — é processo judicial, não bug.

**Conferência contra totais fixados por lei.** `tse.confere` compara o que foi
carregado com 513 deputados federais, 27 senadores em 2022, 54 em 2026. Já pegou
dois erros reais:

1. contagem dobrada por não deduplicar `SQ_CANDIDATO`;
2. em eleição com segundo turno, o mesmo candidato tem duas linhas — a do 1º
   turno diz "2º TURNO" e só a do 2º diz "ELEITO". Ficar com a primeira derrubava
   os governadores de 2022 de 27 para 21.

**A API `/despesas` da Câmara responde vazio.** Use o CSV anual, que ainda traz
o link do PDF de cada nota fiscal.

**Votações e eventos recusam janela maior que 3 meses** (HTTP 400). O conector
fatia o período sozinho, em janelas de 85 dias.

**O id da votação é `<id da proposição>-<sequência>`.** O campo oficial
`uriProposicaoObjeto` vem nulo em três quartos dos casos; usar o prefixo leva o
vínculo com a matéria de 24% para 100%.

**Só 2% das votações são nominais.** Das 7.436 de 2026, apenas 155 registram
quem votou o quê. `votacao.tipo` separa as duas, e a tela precisa dizer isso em
vez de sugerir uma cobertura que não existe.

**O TSE não divulga CPF de candidato municipal.** O campo vem com o código
`-4`, de "não divulgável" — nos federais de 2022 vem completo. A ponte do CPF,
que resolve os 513 deputados, não serve no município: lá a chave é o
`SQ_CANDIDATO`, e `pessoa.cpf_hash` fica nulo. Quando chegar dado de câmara
municipal raspado, o cruzamento será por nome dentro do município — é para isso
que a fila de revisão existe.

**Município recém-criado não tem `microrregiao` na API do IBGE.** Filtrar por
esse campo descarta em silêncio: foi assim que Boa Esperança do Norte (MT)
sumiu e os eleitos de lá ficaram sem município. São 5.571, não 5.570.

**Vinte e um municípios não têm resultado de vereador publicado.** Todas as
linhas vêm com `#NULO`, afetando 2.503 candidaturas — entre elas Ananindeua
(PA) e Jataí (GO). Não é falha de carga: o arquivo do TSE não diz quem foi
eleito. Brasília e Fernando de Noronha aparecem na mesma lista por motivo
legítimo: não têm vereadores.

**Na pauta, a matéria está em `proposicaoRelacionada_`.** O campo `proposicao_`
aponta para o parecer do relator (PRL) em 259 dos 403 itens. Lendo o campo certo,
a pauta vira 281 PLs em vez de 259 pareceres sem conteúdo — é a diferença entre
anunciar "PRL 1/0" e "PL 6198/2025".

**Uma matéria rende várias votações no mesmo dia** (destaque, emenda, primeiro e
segundo turno). Alertar por votação gerava 5 avisos para a mesma PEC. O motor
agrupa por matéria e dia e anuncia a votação mais cheia, que é a decisiva.

**Suplente e ex-deputado também votam.** 54 pessoas fora dos 513 atuais votaram
em 2026. Ignorá-las perderia 4% dos votos e faria o placar não fechar — elas
entram com mandato `encerrado`.

## Como subir a API

```bash
export PYTHONPATH=src
./.venv/bin/uvicorn plataforma.api:app --reload --port 8000
```

`/saude` · `/ufs` · `/congresso` · `/deputados?uf=BA` · `/deputados/{id}` ·
`/votacoes` · `/votacoes/{id}` · `/admin` (painel)

## Front em Next.js

```bash
cd web && npm install
npm run dev          # http://localhost:3000, espera a API na 8000
```

| Rota | Como é servida |
|---|---|
| `/` | mapa do Brasil, estático com revalidação de 15 min |
| `/uf/[sigla]` | 27 páginas pré-renderizadas |
| `/deputado/[id]/[slug]` | sob demanda, com `schema.org/Person` |
| `/congresso` | hemiciclo das 513 cadeiras, estático |

Os componentes de servidor chamam a API direto, então não há CORS e o HTML já
sai pronto — que é o que a busca orgânica exige. A malha do mapa são os 27
estados do IBGE simplificados para 34 KB; a original tem 1 MB.

As cadeiras do hemiciclo ficam neutras e só o partido selecionado acende:
vinte e um partidos em vinte e uma cores ninguém distingue, menos ainda quem
tem daltonismo.

## Alertas

```bash
./.venv/bin/python -m plataforma.cli ingest-eventos --inicio 2026-09-28 --fim 2026-12-27
./.venv/bin/python -m plataforma.cli alertas detectar
./.venv/bin/python -m plataforma.cli alertas fila
./.venv/bin/python -m plataforma.cli alertas enviar --id 23
```

Nada sai sozinho: todo alerta nasce `rascunho` e só vira `enviado` por decisão
humana, registrada em `auditoria`. Sem `FIREBASE_CREDENTIALS` no ambiente, o
despachante imprime no console em vez de notificar.

O filtro pontua por tipo de matéria (PEC 50, MPV 40, PLP 35, PL 25), com bônus
para plenário, votação nominal, placar apertado e watchlist. Abaixo de 40 não
vira nem rascunho. Requerimento é descartado por padrão — é ruído de tramitação,
e é o que mais aparece na pauta.

## Painel de administração

Três superfícies, não uma.

**Importador de CSV.** Para quem opera sozinho, planilha ganha de qualquer tela
de cadastro. Simula, mostra o diff, grava com número de lote e desfaz por
inteiro:

```bash
./.venv/bin/python -m plataforma.cli importar --entidade competencia \
    --arquivo templates/competencia.csv                 # simula
./.venv/bin/python -m plataforma.cli importar --entidade competencia \
    --arquivo templates/competencia.csv --ator seu-nome --confirmar
./.venv/bin/python -m plataforma.cli reverter --lote <uuid> --ator seu-nome
```

Entidades prontas: `competencia`, `orgao_municipal`, `pessoa`, `mandato`.
Faltam `gabinete`, `despesa` e `proposicao` — mesma máquina, só a especificação.

Valida dígito verificador de CPF, existência do código IBGE, formato de data,
numérico e domínio dos enums, sempre com o número da linha. Nada é gravado se
houver qualquer erro.

Toda linha importada nasce com `fonte_registro.tipo = 'manual'`, quem inseriu e
o link do documento. Dado manual precisa parecer dado manual.

**Mesa de alertas** em `/admin`. Lista a fila, e cada alerta espera notificar,
aprovar ou descartar. A decisão vai para `auditoria` com ator e horário.

**Fila de identidade** em `/admin/identidades`. Hoje está vazia porque a ponte
do CPF resolveu os 513 — vazia significa resolvido, não quebrado.

### Autenticação

Não escrevemos autenticação: a identidade vem de um provedor externo e o código
só decide o que a pessoa pode fazer, sempre verificando no servidor.

| Ambiente | Mecanismo |
|---|---|
| Produção | `FIREBASE_CREDENTIALS` — ID token com claim de administrador |
| Desenvolvimento | `ADMIN_TOKEN` — segredo de 32+ caracteres, sem usuário nem senha |

O cidadão nunca passa por aqui: o app funciona anônimo, e onde a pessoa mora
fica no aparelho, não no servidor.

## Próximo passo

Verificação real do Firebase (depende das credenciais do projeto), as três
entidades que faltam no importador, páginas de município e a cobertura
declarada por município — hoje a ausência de vereador é indistinguível de
"não publicado".

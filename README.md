# Plataforma de Transparência Política

Dados de quem foi eleito no Brasil, quanto gasta, como vota e para onde vai o
dinheiro público — a partir das fontes oficiais.

Arquitetura e decisões: https://claude.ai/artifact/CqwwuhRpr44FmD6G8MhBoC

## Estado atual — Fases 0 a 4

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
| Tramitação | 19.694 etapas em 1.124 proposições; 8.162 viraram marco, 11.532 eram ruído |
| Leis concluídas | 88 rastreadas do protocolo ao Diário Oficial (30 leis, 55 decretos legislativos, 2 emendas, 1 lei complementar) |
| Autoria e relatoria | 2.607 registros; 1.305 relatores extraídos do despacho |
| Cobertura declarada | 11.142 pares município×cargo: 11.103 publicados, 35 não publicados, 4 não se aplicam |
| População | Censo 2022 e estimativa 2021 nos 5.571 municípios e 27 estados |
| Conteúdo educativo | 78 atribuições de cargo, todas com artigo citado |
| Reconhecimento de etapa | 95,3% por código, 4,7% por regra de texto (a parte frágil) |
| Fontes levantadas | federal testado; 4 de 27 estados levantados; 510 municípios com diário indexado |

**513 de 513 deputados ligados ao TSE**, sendo 511 por CPF e 2 por nome dentro
da mesma UF. Fila de revisão vazia.

Além disso: API de leitura em FastAPI (`src/plataforma/api.py`), painel de
administração com quatro filas e front em Next.js (`web/`) com 44 páginas.

### A vida de uma lei

`src/plataforma/tramitacao.py` reduz os 235 tipos de movimentação da Câmara a
12 marcos que uma cidadã entende, em sete fases do protocolo à sanção. O PL
1087/2025 tem 153 movimentações e vira 10 blocos legíveis.

**O ponto mais frágil do projeto está aqui, e é documentado no arquivo.** Os
marcos mais importantes não vêm no código da movimentação: "Remessa ao Senado
Federal" veio no código genérico 190 (Expedição de Documento) e "remessa da
matéria à sanção" veio no 100 (Apresentação de Proposição). Existe um código
128 para a ida ao Senado — aquele PL não usou. Então o reconhecimento tem duas
camadas, código e texto, e cada etapa reconhecida por texto fica marcada com
`metodo='texto'` no banco: são 8% dos marcos, e são exatamente as que param de
funcionar caladas se a fonte reescrever a frase.

Contra isso há três defesas:

```bash
./.venv/bin/python scripts/testa_marcos.py          # 21 casos reais, sem rede
./.venv/bin/python scripts/valida_tramitacao.py --amostra 180   # acordo com a API ao vivo
```

e a tabela `divergencia_tramitacao`, que registra toda proposição cuja situação
declarada pela fonte não aparece na trilha. Na primeira rodada ela acusou três
divergências em 70 proposições, e as três eram defeito meu.

O Senado entra por `/dadosabertos/processo` — e não pelo `/materia`, que foi
marcado para desativação em 01/02/2026 e ainda responde, o que torna fácil
construir em cima dele por engano. O serviço novo entrega estruturado o que na
Câmara só existe como texto livre: `normaGerada`, `situacaoAtual`, `objetivo`.
Quando as duas fontes divergem sobre o número da lei, vale a do Senado — campo
publicado é mais confiável que expressão regular.

## Como rodar

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env          # defina CPF_SALT

export PYTHONPATH=src
./.venv/bin/python -m plataforma.cli ingest-camara --ano 2026
./.venv/bin/python -m plataforma.cli ingest-tse    --ano 2022
./.venv/bin/python -m plataforma.cli resolve       --ano 2022

# fase 4: a vida das leis e o limite de cada cargo
./.venv/bin/python -m plataforma.cli leis --inicio 2026-10-20 --fim 2026-10-23
./.venv/bin/python -m plataforma.cli cargos
```

`leis` é a única carga pensada para rodar todo dia. Ela usa o filtro por data
de *tramitação* da API: numa janela de dez dias voltam ~4.400 proposições, e
entre elas aparece coisa apresentada em 2003 que se mexeu agora. Sem isso a
atualização diária teria que varrer o acervo inteiro; com isso são ~440
proposições por dia, uns minutos de execução. Em espaço, ~420 mil etapas por
ano a ~700 bytes dão cerca de 300 MB/ano — dez anos de acervo cabem em 10 GB.

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

## O limite de cada cargo

É o objetivo central da plataforma e a única parte sem API: texto escrito por
gente, com o artigo citado ao lado. Fica em `db/009_atribuicoes_seed.sql`, nasce
com `revisado=false` e só perde o aviso de "em revisão" na tela pública depois
que alguém aprovar no painel.

Duas honestidades que o schema carrega:

- O limite do vereador não está só na Constituição. O art. 29 manda cada
  município se reger pela sua Lei Orgânica — são 5.571 textos. A coluna
  `abrangencia` separa o que vale para todo o país do que depende da lei local.
- O critério do "não pode" não é proibição jurídica: é o que as pessoas cobram
  de quem não tem como atender. Vereador não asfalta rua, prefeito não comanda
  a Polícia Militar, deputado federal não tapa buraco de bairro.

### Um erro que vale guardar

Dois desses limites são número, não texto: o art. 29, IV fixa o teto de
cadeiras por faixa de população, em 24 degraus. Com a população do IBGE, dá
para conferir as 5.571 câmaras do país.

A primeira versão comparava contra o Censo 2022 e acusava **34 câmaras** de
estourar o teto. Estava errada. O número de vagas é fixado *antes* da eleição,
com a população vigente naquele momento — e entre a estimativa de 2021 e o
Censo 2022 muitos municípios encolheram. Rio Preto da Eva (AM) caiu de 34.856
para 24.936 habitantes, o que muda o teto de 13 para 11 cadeiras sem que
ninguém tenha feito nada.

Trinta das 34 eram legítimas. Publicar aquela lista teria acusado trinta
câmaras em ordem, com a autoridade de um dado oficial.

O resultado honesto, depois de guardar as duas referências:

| | |
|---|---|
| Dentro do teto | 5.513 |
| Dentro do teto pela população da eleição | 29 |
| Acima do teto por qualquer referência | 5 |
| Sem resultado de vereador publicado pelo TSE | 23 |

E as 5 que sobraram não são chamadas de irregulares. Em Braga (RS) o próprio
arquivo do TSE lista 10 vereadores eleitos — 9 por quociente e 1 por média — numa
cidade de 3.268 habitantes. Dez é par, e nenhuma das 24 faixas do art. 29 é par.
A divergência está na fonte, e isso vai para conferência manual, não para a tela
como acusação.

## Cobertura declarada: a diferença entre "não tem" e "não publicaram"

Antes da tabela `cobertura`, município sem vereador no banco era
indistinguível de município cujo resultado o TSE não divulgou. São 23 casos e
três causas:

- **Brasília** não tem vereador nem prefeito por lei — o DF é regido por
  deputados distritais e um governador (CF/88, art. 32).
- **Fernando de Noronha** é distrito estadual de Pernambuco, não município com
  câmara própria.
- **Os outros 21** são lacuna da fonte. Em Ananindeua (PA), 478 mil
  habitantes, o TSE registra 401 candidaturas a vereador e divulga o resultado
  de nenhuma. Em Iporá (GO) nem o prefeito saiu: 165 candidaturas, todas
  `#NULO`.

A classificação não é deduzida da ausência: é contada no arquivo do TSE, por
município e cargo, e a página da cidade mostra o número do lado. Dizer "nenhum
vereador" para Ananindeua sem explicar seria publicar uma afirmação falsa com
cara de dado oficial.

## Importação manual

Sete entidades em `templates/*.csv`, geradas a partir das próprias Specs
(`plataforma.cli templates`) para não divergirem do código.

As três do nível municipal — `gabinete`, `despesa`, `proposicao` — aceitam
`cpf` **ou** `nome_urna` para apontar o mandato. Isso não é conveniência: o TSE
publica `-4` no CPF de candidato municipal, então os 58.174 vereadores do banco
estão com `cpf_hash` nulo e uma chave só por CPF não acharia nenhum. Quando o
nome é ambíguo dentro da cidade, a importação para e diz, em vez de escolher um.

A simulação (sem `--confirmar`) executa os upserts de verdade e desfaz com
`rollback`. Conferir só o formato das colunas não provava nada — o erro caro é
referencial, e ele só aparece quando o `insert` roda.

## Leis estaduais e municipais

A API da Câmara cobre o federal. Acima disso o Brasil não tem padrão, e a
tabela `fonte_legislativa` registra o levantamento com o grau de verificação
explícito — `testado` é "chamei e veio dado", `documentado` é "a casa publica a
documentação e eu não obtive resposta". Tratar os dois como iguais faria o
roadmap mentir sobre o que está pronto.

**Estadual — uma assembleia por vez.** Não existe API única nem agregador
oficial. Verificado em 01/11/2026:

| Casa | Fonte | Tramitação | Verificação |
|---|---|---|---|
| Minas Gerais | API REST v2 | sim | testado — 1.675 PLs de 2025 com autor e ementa |
| São Paulo | XML em massa, 17 MB, diário | **não** | testado — proposituras desde 1996, sem tramitação nem desfecho |
| Paraná | API com `tramites` e `norma-legal` | sim | documentado — o host não respondeu |
| Pernambuco | portal HTML | não | documentado — responde, conteúdo não conferido |
| outras 23 | — | — | não levantado |

A Transparência Internacional avaliou as 27 casas estaduais: só quatro ficaram
em nível "bom" (DF, ES, MG e CE), nenhuma chegou a "ótimo", e dados abertos
está entre os pontos mais fracos.

**Municipal — o buraco de verdade.** 5.571 câmaras, sem padrão, sem API, sem
CSV. O LexML federa apenas 57 câmaras. O único caminho em escala é o diário
oficial: o Querido Diário indexa **510 dos 5.570 municípios (9,2%)**, com busca
em texto completo e sem autenticação.

Mas diário oficial é *texto*, não registro de leis. Uma busca por "lei" em
Salvador devolve 4.823 edições e a lei aparece citada dentro de um despacho
tributário. Virar "quais leis esta cidade aprovou" exige extração, e extração
erra. Por isso o municipal entra pela importação manual revisada, cidade por
cidade — que é o que as entidades `proposicao` e `despesa` do importador fazem.

### O caminho não tem sete etapas em toda esfera

Levantar isso expôs um defeito: o modelo de fases era federal e único. Só o
Congresso tem duas casas. Assembleia legislativa e câmara municipal são
unicamerais, então o projeto vai do plenário direto à sanção:

```
FEDERAL    7 etapas  apresentado → comissões → plenário → casa revisora
                     → plenário revisor → sanção presidencial → lei
ESTADUAL   5 etapas  apresentado → comissões → plenário
                     → sanção do Governador → lei
MUNICIPAL  5 etapas  apresentado → comissões → plenário
                     → sanção do Prefeito → lei
```

Com um caminho único, uma lei estadual mostraria dois degraus que nunca
preenchem e a pessoa leria "faltam quatro etapas" onde faltam duas. Agora
`CAMINHOS` é indexado por esfera, `esfera_de()` deduz do código do IBGE, e o
rótulo da sanção acompanha — dizer "sanção presidencial" numa lei de câmara
municipal seria ensinar errado no lugar onde o projeto quer ensinar.

A página `/cobertura` publica tudo isso, porque ausência de dado pode ser lida
como afirmação: "nenhuma lei do seu estado" tem que significar "ainda não
coletamos", nunca "a assembleia não legislou".

## Próximo passo

Verificação real do Firebase (depende das credenciais do projeto) e o primeiro
conector estadual. Minas Gerais é o melhor candidato: API testada, com
tramitação, e a `fonte_legislativa` já diz onde está.

Depois, por ordem de retorno: ampliar a janela federal de tramitação para 2027
em diante (o acervo histórico só se constrói coletando todo dia), o conector de
São Paulo em massa, e o piloto de extração de gazeta em uma cidade coberta pelo
Querido Diário — com timebox, porque extração de PDF é poço sem fundo.

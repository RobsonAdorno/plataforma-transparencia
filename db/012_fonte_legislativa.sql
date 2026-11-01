-- Onde existe fonte de lei para cada ente, e de que qualidade.
--
-- O nivel federal tem uma API boa e documentada. Acima disso o Brasil nao tem
-- padrao nenhum: 27 assembleias legislativas, cada uma com o seu jeito, e
-- 5.571 camaras municipais sem nada. Nao existe agregador oficial que resolva.
--
-- Esta tabela e o registro desse levantamento, com o grau de verificacao
-- explicito. Serve para tres coisas: dizer na tela o que esta coberto, dizer o
-- que NAO esta (que e a parte honesta), e guiar em que ordem construir.
--
-- `verificacao` nao e enfeite. 'testado' significa que eu chamei o endpoint e
-- vi dado voltar. 'documentado' significa que a casa publica a documentacao
-- mas eu nao consegui resposta - caso do Parana, cuja API e a mais completa
-- que achei e cujo host nao resolveu daqui. Tratar os dois como iguais faria o
-- roadmap mentir sobre o que esta pronto para usar.

begin;

create table if not exists fonte_legislativa (
  ente_codigo  text    not null references ente(codigo_ibge),
  escopo       text    not null check (escopo in ('proposicao','norma','tramitacao','gazeta')),
  tipo         text    not null check (tipo in ('API','BULK','GAZETA','HTML','NENHUMA')),
  url          text,
  formato      text,
  -- 'testado' = chamei e veio dado. 'documentado' = a casa documenta mas nao
  -- obtive resposta. 'ausente' = procurei e nao existe.
  verificacao  text    not null default 'ausente'
                       check (verificacao in ('testado','documentado','ausente')),
  tem_tramitacao boolean not null default false,
  observacao   text,
  verificado_em date,
  primary key (ente_codigo, escopo)
);
create index if not exists ix_fonte_legislativa_tipo
  on fonte_legislativa (tipo, verificacao);

-- ---------------------------------------------------- o que foi verificado
--
-- Levantamento de 2026-11-01. Os codigos de ente sao os do IBGE: '0' e a
-- Uniao, dois digitos sao estado.

insert into fonte_legislativa
  (ente_codigo, escopo, tipo, url, formato, verificacao, tem_tramitacao,
   observacao, verificado_em) values

-- Uniao: a unica esfera com cobertura completa hoje.
('0','proposicao','API','https://dadosabertos.camara.leg.br/api/v2','JSON','testado',true,
 'API v2 da Camara, com /tramitacoes e /autores por proposicao. Base do que ja esta carregado.','2026-11-01'),
('0','norma','API','https://legis.senado.leg.br/dadosabertos/processo','JSON','testado',true,
 'Servico /processo do Senado: normaGerada estruturada. O /materia antigo foi desativado em 01/02/2026.','2026-11-01'),

-- Minas Gerais: a melhor API estadual que respondeu.
('31','proposicao','API','https://dadosabertos.almg.gov.br/api/v2','JSON','testado',true,
 '1.675 projetos de lei de 2025, com autor e ementa. O endpoint /api/v1 redireciona para /api/v2.','2026-11-01'),

-- Sao Paulo: volume grande, mas so o cadastro da propositura.
('35','proposicao','BULK',
 'https://www.al.sp.gov.br/repositorioDados/processo_legislativo/proposituras.zip',
 'XML','testado',false,
 '17 MB, proposituras desde 1996, atualizacao diaria. Traz ementa, numero, ano e datas - nao traz tramitacao nem desfecho.','2026-11-01'),

-- Parana: a API mais completa que encontrei, e a que nao consegui alcancar.
('41','proposicao','API','http://webservices.assembleia.pr.leg.br/api/public','JSON','documentado',true,
 'Documentacao propria descreve /proposicao/{codigo} com tramites embutidos e /norma-legal com movimentacoes de sancao e vinculo de volta a proposicao - o modelo mais parecido com o federal. O host nao resolveu nos testes de 01/11/2026.','2026-11-01'),

-- Pernambuco: portal responde, conteudo nao conferido.
('26','proposicao','HTML','https://dadosabertos.alepe.pe.gov.br','HTML','documentado',false,
 'O host responde HTTP 200. Nao verifiquei se publica proposicao em formato legivel por maquina.','2026-11-01')

on conflict (ente_codigo, escopo) do update set
  tipo=excluded.tipo, url=excluded.url, formato=excluded.formato,
  verificacao=excluded.verificacao, tem_tramitacao=excluded.tem_tramitacao,
  observacao=excluded.observacao, verificado_em=excluded.verificado_em;

-- Os 21 estados restantes entram como ausentes ate alguem conferir um por um.
-- Linha em branco seria pior: sugeriria que a pergunta nao foi feita.
insert into fonte_legislativa
  (ente_codigo, escopo, tipo, verificacao, observacao, verificado_em)
select e.codigo_ibge, 'proposicao', 'NENHUMA', 'ausente',
       'Ainda nao levantado. A Transparencia Internacional avaliou as 27 casas '
       'legislativas estaduais e so quatro ficaram em nivel "bom" (DF, ES, MG e CE); '
       'nenhuma chegou a "otimo", e dados abertos esta entre os pontos mais fracos.',
       date '2026-11-01'
  from ente e
 where e.nivel = 'estado'
on conflict (ente_codigo, escopo) do nothing;

-- Municipal: a gazeta e o unico caminho em escala, e cobre 9% do pais.
insert into fonte_legislativa
  (ente_codigo, escopo, tipo, url, formato, verificacao, tem_tramitacao,
   observacao, verificado_em)
select e.codigo_ibge, 'gazeta', 'GAZETA',
       'https://api.queridodiario.org.br/gazettes?territory_ids=' || e.codigo_ibge,
       'PDF/texto', 'ausente', false,
       'Querido Diario cobre 510 dos 5.570 municipios com diario oficial '
       'indexado. A cobertura real e preenchida pelo coletor; esta linha so '
       'registra que a pergunta foi feita para este municipio.',
       date '2026-11-01'
  from ente e
 where e.nivel = 'municipio'
on conflict (ente_codigo, escopo) do nothing;

commit;

-- Cobertura declarada: a diferenca entre "nao tem" e "nao publicaram".
--
-- Ate aqui, municipio sem vereador no banco era indistinguivel de municipio
-- cujo resultado o TSE nao divulgou. Sao 23 casos, e tres causas diferentes:
--
--   Brasilia (DF)            - nao tem vereador nem prefeito por lei: o DF e
--                              regido por deputados distritais e um governador
--   Fernando de Noronha (PE) - distrito estadual, administrado por Pernambuco
--   os outros 21             - o arquivo do TSE traz '#NULO' no resultado.
--                              Em Ananindeua (PA), com 478 mil habitantes, sao
--                              401 candidaturas a vereador sem resultado. Em
--                              Ipora (GO) nem o prefeito saiu: 165 candidaturas,
--                              todas '#NULO'
--
-- Numa plataforma de transparencia a tela precisa saber qual dos tres e, porque
-- "nenhum vereador" dito sem explicacao e uma afirmacao falsa sobre a cidade.

begin;

create table if not exists cobertura (
  ente_codigo   text    not null references ente(codigo_ibge),
  cargo         text    not null,
  ano_eleicao   integer not null,
  situacao      text    not null
                        check (situacao in ('publicado','nao_publicado','nao_se_aplica')),
  eleitos       integer not null default 0,
  candidaturas  integer not null default 0,
  -- Quantas linhas vieram sem resultado na fonte. E a prova do que a tela
  -- afirma: nao e deducao a partir da ausencia, e contagem do que falta.
  sem_resultado integer not null default 0,
  motivo        text,
  fonte         text    not null,
  verificado_em timestamptz not null default now(),
  primary key (ente_codigo, cargo, ano_eleicao)
);
create index if not exists ix_cobertura_situacao
  on cobertura (situacao, cargo) where situacao <> 'publicado';

commit;

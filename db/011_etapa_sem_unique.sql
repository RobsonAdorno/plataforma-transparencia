-- Remove a restricao de unicidade de `etapa`. Ela estava errada sobre a fonte.
--
-- Eu assumi que (proposicao, fonte, sequencia, cod_tipo, data_hora) identificava
-- uma movimentacao. Nao identifica. A Camara publica movimentacoes distintas
-- empatadas nos cinco campos - no PL 1087/2025 o codigo 196 aparece duas vezes
-- no mesmo instante, com despachos diferentes:
--
--   "Aprovado o requerimento nº 3382/2025, que solicita urgência para o PL 1087/2025."
--   "Alteração do Regime de Tramitação desta proposição em virtude da Aprovação
--    do REQ 3382/2025."
--
-- Sao dois fatos reais: a aprovacao do requerimento e a mudanca de regime que
-- ela causou. Guardar so um perde informacao; a restricao fazia a carga
-- estourar na primeira vez que a janela pegava um par desses. Uma janela de
-- quatro dias passou, a de cinco semanas nao.
--
-- E a restricao nao protegia nada: _grava_etapas() apaga a trilha daquela casa
-- antes de reinserir, justamente porque a sequencia do Senado vem nula e nulo
-- nao conflita com nulo em Postgres. A idempotencia vem do delete, nao do
-- indice.

begin;

alter table etapa drop constraint if exists
  etapa_proposicao_id_fonte_sequencia_cod_tipo_data_hora_key;

commit;

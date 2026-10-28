-- O item de pauta frequentemente aponta para o parecer do relator (PRL), e a
-- materia de verdade fica em proposicaoRelacionada_. Guardamos a materia como
-- proposicao_id e o parecer ao lado, que e o que diz o que o relator defende.
begin;
alter table pauta_item add column if not exists relator        text;
alter table pauta_item add column if not exists texto_parecer  text;
alter table pauta_item add column if not exists titulo         text;
commit;

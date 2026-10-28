-- O TSE nao divulga CPF de candidato municipal (vem o codigo -4). Para esses,
-- a chave e o proprio SQ_CANDIDATO: identificador exato da fonte, nao palpite.
-- O metodo precisa dizer isso em vez de se disfarcar de 'cpf'.
begin;
alter table identidade_externa drop constraint if exists identidade_externa_metodo_check;
alter table identidade_externa add constraint identidade_externa_metodo_check
  check (metodo in ('cpf','id_fonte','nome_nascimento','nome_municipio','manual'));
commit;

-- Os temas pelos quais a reclamacao e roteada.
--
-- Esta tabela e o cerebro do canal: a pessoa descreve um poste queimado e a
-- plataforma precisa saber que isso e da prefeitura, nao do governador nem do
-- deputado federal. Sem isso o canal seria so uma caixa de texto.
--
-- Duas honestidades no desenho:
--
-- 1. Tema pode pertencer a mais de uma esfera, e isso nao e defeito. Saude e
--    competencia comum (CF art. 23, II): a UBS do bairro e municipal, o
--    hospital de referencia e estadual, e a alta complexidade e pactuada. O
--    indice unico inclui a esfera justamente para permitir a linha dupla, e a
--    tela mostra as duas em vez de escolher uma e errar metade das vezes.
--
-- 2. Saneamento e o caso que mais engana. A competencia e municipal por
--    interesse local (CF art. 30, V), mas quase todo municipio delegou o
--    servico a uma companhia estadual. Quem reclama de falta de agua precisa
--    procurar a concessionaria, e quem reclama que a cidade nao cobra a
--    concessionaria precisa procurar a prefeitura. Os dois estao certos.

begin;

insert into competencia (tema, esfera, cargo_responsavel, descricao, base_legal) values

-- ------------------------------------------------------------- MUNICIPAL
('Iluminação pública','MUNICIPAL','PREFEITO',
 'Instalação, troca de lâmpada e manutenção da iluminação em vias e praças, custeada pela COSIP que vem na conta de luz.',
 'CF/88, art. 30, V e art. 149-A'),
('Buraco na rua e pavimentação','MUNICIPAL','PREFEITO',
 'Tapar buraco, recapear e pavimentar vias urbanas do município.','CF/88, art. 30, I e V'),
('Coleta de lixo','MUNICIPAL','PREFEITO',
 'Coleta domiciliar, varrição e destinação dos resíduos urbanos.',
 'CF/88, art. 30, V; Lei 11.445/2007'),
('Mato alto e terreno abandonado','MUNICIPAL','PREFEITO',
 'Notificar e multar o proprietário, e fazer a limpeza quando o terreno é público.',
 'CF/88, art. 30, VIII; Código de Posturas municipal'),
('Calçada e acessibilidade','MUNICIPAL','PREFEITO',
 'Exigir e fiscalizar calçada em condição de uso; a obra em frente a imóvel privado costuma ser do proprietário, mas quem fiscaliza é a prefeitura.',
 'CF/88, art. 30, VIII; Lei 13.146/2015'),
('Praça, parque e área de lazer','MUNICIPAL','PREFEITO',
 'Manutenção de praças, parques e equipamentos públicos de lazer do município.','CF/88, art. 30, I'),
('Transporte coletivo urbano','MUNICIPAL','PREFEITO',
 'Organizar e fiscalizar o ônibus municipal, incluindo itinerário, tarifa e frota. A Constituição dá esse serviço expressamente ao município.',
 'CF/88, art. 30, V'),
('Creche e pré-escola','MUNICIPAL','PREFEITO',
 'Oferecer educação infantil de 0 a 5 anos. Vaga em creche é obrigação municipal e exigível na Justiça.',
 'CF/88, art. 30, VI e art. 208, IV; Lei 9.394/1996'),
('Escola de ensino fundamental','MUNICIPAL','PREFEITO',
 'Manter o ensino fundamental, com apoio técnico e financeiro da União e do estado.',
 'CF/88, art. 30, VI e art. 211, §2º'),
('Posto de saúde e atenção básica','MUNICIPAL','PREFEITO',
 'UBS, equipe de saúde da família, vacina e consulta de rotina são do município.',
 'CF/88, art. 30, VII e art. 198'),
('Saneamento: água e esgoto','MUNICIPAL','PREFEITO',
 'A competência é municipal, mas quase todo município delegou o serviço a uma companhia estadual. Reclame na concessionária para resolver o problema, e na prefeitura para cobrar quem fiscaliza o contrato.',
 'CF/88, art. 30, V; Lei 11.445/2007; Lei 14.026/2020'),
('Alagamento e drenagem','MUNICIPAL','PREFEITO',
 'Boca de lobo, galeria pluvial e drenagem urbana; a Defesa Civil municipal responde na emergência.',
 'CF/88, art. 30, V; Lei 12.608/2012'),
('Obra irregular e fiscalização de posturas','MUNICIPAL','PREFEITO',
 'Construção sem alvará, uso do solo em desacordo e barulho acima do permitido são fiscalizados pela prefeitura.',
 'CF/88, art. 30, VIII; Código de Obras municipal'),
('Poda de árvore','MUNICIPAL','PREFEITO',
 'Poda, remoção e plantio em via pública dependem de autorização e execução municipal.','CF/88, art. 30, I e art. 23, VI'),
('Semáforo e sinalização de trânsito','MUNICIPAL','PREFEITO',
 'Em via municipal, sinalizar, fiscalizar e aplicar multa é do município. Em rodovia estadual ou federal que atravessa a cidade, não é.',
 'Lei 9.503/1997 (CTB), art. 24'),
('Animais de rua e zoonoses','MUNICIPAL','PREFEITO',
 'Controle de zoonoses, castração e recolhimento são serviços locais de vigilância em saúde.',
 'CF/88, art. 30, VII e art. 23, II'),
('IPTU, ISS e ITBI','MUNICIPAL','PREFEITO',
 'Lançamento, cobrança e revisão dos tributos municipais.','CF/88, art. 156'),
('Feira e comércio ambulante','MUNICIPAL','PREFEITO',
 'Autorizar e fiscalizar feira livre e ambulante é ordenamento do uso do espaço público local.','CF/88, art. 30, I e VIII'),
('Fiscalização das contas da prefeitura','MUNICIPAL','VEREADOR',
 'Suspeita de irregularidade no gasto municipal vai à Câmara, que fiscaliza o prefeito com auxílio do Tribunal de Contas do Estado.',
 'CF/88, art. 31'),

-- -------------------------------------------------------------- ESTADUAL
('Segurança pública e policiamento','ESTADUAL','GOVERNADOR',
 'Polícia Militar e Polícia Civil são do estado. A guarda municipal protege bens e serviços do município e não faz policiamento ostensivo geral.',
 'CF/88, art. 144, §§ 4º, 5º e 6º'),
('Rodovia estadual','ESTADUAL','GOVERNADOR',
 'Buraco, sinalização e manutenção em rodovia com sigla do estado (ex.: SP-, MG-, BA-).','CF/88, art. 25, §1º'),
('Escola de ensino médio','ESTADUAL','GOVERNADOR',
 'O ensino médio é prioridade do estado, mesmo quando a escola fica na sua rua.','CF/88, art. 211, §3º'),
('Hospital e UPA estaduais','ESTADUAL','GOVERNADOR',
 'Hospital de referência, UPA estadual e média e alta complexidade são do estado.','CF/88, art. 198 e art. 23, II'),
('Corpo de Bombeiros','ESTADUAL','GOVERNADOR',
 'O Corpo de Bombeiros Militar é força auxiliar do estado.','CF/88, art. 144, §5º'),
('Sistema prisional','ESTADUAL','GOVERNADOR',
 'Cadeia pública e penitenciária estadual, incluindo vaga, transporte e condição de custódia.','CF/88, art. 24, I e art. 144'),
('Detran: habilitação e licenciamento','ESTADUAL','GOVERNADOR',
 'CNH, licenciamento, vistoria e multa de rodovia estadual passam pelo Detran do estado.','Lei 9.503/1997 (CTB), art. 22'),
('ICMS e IPVA','ESTADUAL','GOVERNADOR',
 'Cobrança, isenção e revisão dos tributos estaduais.','CF/88, art. 155'),

-- --------------------------------------------------------------- FEDERAL
('Rodovia federal (BR)','FEDERAL','PRESIDENTE',
 'Rodovia com sigla BR- é federal, mesmo atravessando a sua cidade. A fiscalização de trânsito nela é da Polícia Rodoviária Federal.',
 'CF/88, art. 21, XII, c; Lei 9.503/1997, art. 20'),
('INSS, aposentadoria e benefício','FEDERAL','PRESIDENTE',
 'Perícia, benefício, aposentadoria e BPC são do INSS.','CF/88, art. 201; Lei 8.213/1991'),
('Receita Federal: CPF e imposto de renda','FEDERAL','PRESIDENTE',
 'CPF, declaração de IR e tributos federais.','CF/88, art. 153'),
('Passaporte e Polícia Federal','FEDERAL','PRESIDENTE',
 'Passaporte, imigração e polícia judiciária da União.','CF/88, art. 21, XIII e art. 144, §1º'),
('Energia elétrica','FEDERAL','PRESIDENTE',
 'Falta de luz e tarifa são da concessionária, regulada pela ANEEL, que é federal — não da prefeitura. A iluminação da rua, porém, é municipal.',
 'CF/88, art. 21, XII, b; Lei 9.427/1996'),
('Telefone e internet','FEDERAL','PRESIDENTE',
 'Telecomunicações são serviço federal, regulado pela ANATEL.','CF/88, art. 21, XI; Lei 9.472/1997'),
('Universidade e instituto federal','FEDERAL','PRESIDENTE',
 'IFES e Institutos Federais integram a rede federal de ensino.','CF/88, art. 211, §1º'),
('Correios','FEDERAL','PRESIDENTE',
 'Serviço postal é monopólio da União.','CF/88, art. 21, X'),
('Aeroporto e porto','FEDERAL','PRESIDENTE',
 'Infraestrutura aeroportuária e portuária é da União, ainda que dentro do município.','CF/88, art. 21, XII, c e f'),

-- Saude e educacao sao competencia COMUM: a mesma reclamacao pode ter dois
-- enderecos certos, e esconder isso faria a pessoa procurar o errado.
('Saúde: média e alta complexidade','ESTADUAL','GOVERNADOR',
 'Cirurgia, exame especializado e internação de referência: o município faz a atenção básica, o estado a média e alta complexidade. Competência comum.',
 'CF/88, art. 23, II e art. 198'),
('Saúde: média e alta complexidade','FEDERAL','PRESIDENTE',
 'A União financia e coordena o SUS nacionalmente, e responde pelos hospitais federais.',
 'CF/88, art. 23, II e art. 198, §1º')

on conflict (lower(tema), esfera, cargo_responsavel) do update set
  descricao = excluded.descricao, base_legal = excluded.base_legal;

commit;

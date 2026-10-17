/**
 * Check House — API de consulta de clientes
 *
 * Integra o CNJ DataJud (gratuito) para buscar processos judiciais por CPF
 * em todos os principais tribunais brasileiros.
 *
 * Pré-requisito: chave gratuita em https://datajud-wiki.cnj.jus.br/api-publica/acesso
 */

const express = require('express');
const cors    = require('cors');
const path    = require('path');
require('dotenv').config();

const app  = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());
// Serve o PWA estático pela mesma origem
app.use(express.static(path.join(__dirname, '..')));

// ---------------------------------------------------------------------------
// Configuração CNJ DataJud
// ---------------------------------------------------------------------------
const CNJ_API_KEY = process.env.CNJ_API_KEY || '';
const CNJ_BASE    = 'https://api-publica.datajud.cnj.jus.br';

// Tribunais consultados (ajuste conforme a região dos seus clientes)
const TRIBUNAIS_ESTADUAIS = [
  'tjsp','tjrj','tjmg','tjrs','tjba','tjpr','tjsc','tjgo',
  'tjpe','tjce','tjdf','tjma','tjpb','tjrn','tjal','tjse',
  'tjmt','tjms','tjto','tjro','tjac','tjam','tjamazonas',
  'tjrr','tjap','tjpa','tjpi','tjes'
];
const TRIBUNAIS_FEDERAIS  = ['trf1','trf2','trf3','trf4','trf5','trf6'];
const TRIBUNAIS_TRABALHO  = ['trt1','trt2','trt3','trt4','trt9','trt15'];
const SUPERIORES          = ['stj'];

const TODOS_TRIBUNAIS = [
  ...TRIBUNAIS_ESTADUAIS,
  ...TRIBUNAIS_FEDERAIS,
  ...TRIBUNAIS_TRABALHO,
  ...SUPERIORES,
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function validarCpf(digits) {
  if (digits.length !== 11 || /^(\d)\1+$/.test(digits)) return false;
  const calc = (n) => {
    let s = 0;
    for (let i = 0; i < n; i++) s += parseInt(digits[i]) * (n + 1 - i);
    const r = (s * 10) % 11;
    return r === 10 || r === 11 ? 0 : r;
  };
  return calc(9) === parseInt(digits[9]) && calc(10) === parseInt(digits[10]);
}

async function consultarTribunal(tribunal, cpfDigits) {
  const url  = `${CNJ_BASE}/api_publica_${tribunal}/_search`;
  const body = {
    size: 20,
    query: {
      bool: {
        should: [
          { term: { 'partes.cpfCnpj': cpfDigits } },
          { match: { 'partes.docPrincipal': cpfDigits } },
        ],
        minimum_should_match: 1,
      },
    },
    _source: [
      'numeroProcesso','dataAjuizamento','classe.nome',
      'assunto','orgaoJulgador.nome','movimentos',
      'partes','grau','tribunal.nome',
    ],
  };

  const controller = new AbortController();
  const timeout    = setTimeout(() => controller.abort(), 8000);

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `ApiKey ${CNJ_API_KEY}`,
        'Content-Type':  'application/json',
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!resp.ok) return [];

    const data = await resp.json();
    return (data.hits?.hits || []).map(h => {
      const s = h._source || {};
      return {
        tribunal:         tribunal.toUpperCase(),
        tribunalNome:     s.tribunal?.nome || tribunal.toUpperCase(),
        numero:           s.numeroProcesso || '—',
        classe:           s.classe?.nome   || '—',
        assunto:          (s.assunto || [])[0]?.nome || '—',
        orgaoJulgador:    s.orgaoJulgador?.nome || '—',
        grau:             s.grau || '—',
        dataAjuizamento:  s.dataAjuizamento || null,
        ultimoMovimento:  (s.movimentos || [])[0]?.nome || '—',
      };
    });
  } catch {
    clearTimeout(timeout);
    return [];
  }
}

// ---------------------------------------------------------------------------
// CNJ BNMP — Banco Nacional de Monitoramento de Prisões
// Portal público: https://portalbnmp.cnj.jus.br
// ---------------------------------------------------------------------------
const BNMP_BASE = 'https://portalbnmp.cnj.jus.br/bnmpportal/api';

async function consultarBNMP(cpf) {
  const controller = new AbortController();
  const timeout    = setTimeout(() => controller.abort(), 10000);

  try {
    // Primeiro obtém token público do portal BNMP
    const tokenResp = await fetch(`${BNMP_BASE}/login/auth`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'guest', password: 'guest' }),
      signal: controller.signal,
    });

    let authHeader = '';
    if (tokenResp.ok) {
      const tokenData = await tokenResp.json().catch(() => ({}));
      if (tokenData.token) authHeader = `Bearer ${tokenData.token}`;
    }

    // Busca mandados pelo CPF
    const searchResp = await fetch(`${BNMP_BASE}/pesquisa-pecas/filter/penal`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(authHeader ? { 'Authorization': authHeader } : {}),
      },
      body: JSON.stringify({
        cpf,
        pagina: 1,
        tamanhoPagina: 20,
        buscaOrgaoJulgador: {},
      }),
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!searchResp.ok) return { ok: false, erro: `BNMP HTTP ${searchResp.status}`, mandados: [] };

    const data = await searchResp.json();
    const hits  = data.content || data.hits?.hits || data.data || [];

    const mandados = hits.map(h => {
      const s = h._source || h;
      return {
        tipo:      s.tipoPeca?.descricao || s.tipo || 'Mandado de prisão',
        situacao:  s.situacaoMandado?.descricao || s.situacao || '—',
        tribunal:  s.orgaoJulgador?.tribunal?.sigla || s.tribunal || '—',
        orgao:     s.orgaoJulgador?.descricao || '—',
        dataExpedicao: s.dataExpedicao || s.dataPeca || null,
        nome:      s.nome || s.nomeParte || '—',
      };
    });

    return {
      ok: true,
      totalMandados: mandados.length,
      mandados,
    };
  } catch (e) {
    clearTimeout(timeout);
    return { ok: false, erro: e.message, mandados: [] };
  }
}

// ---------------------------------------------------------------------------
// Rotas
// ---------------------------------------------------------------------------

// Saúde do servidor
app.get('/api/status', (_req, res) => {
  res.json({
    ok: true,
    cnj_configurado: !!CNJ_API_KEY,
    tribunais: TODOS_TRIBUNAIS.length,
    timestamp: new Date().toISOString(),
  });
});

// BNMP — mandados de prisão ativos
app.get('/api/bnmp/:cpf', async (req, res) => {
  const cpf = req.params.cpf.replace(/\D/g, '');
  if (!validarCpf(cpf)) return res.status(400).json({ erro: 'CPF inválido' });

  const resultado = await consultarBNMP(cpf);
  res.json({ cpf, ...resultado });
});

// Consulta principal: processos por CPF
app.get('/api/consultar-cpf/:cpf', async (req, res) => {
  const cpf    = req.params.cpf.replace(/\D/g, '');
  const cpfFmt = `${cpf.slice(0,3)}.${cpf.slice(3,6)}.${cpf.slice(6,9)}-${cpf.slice(9)}`;

  if (!validarCpf(cpf)) {
    return res.status(400).json({ erro: 'CPF inválido' });
  }

  if (!CNJ_API_KEY) {
    return res.status(503).json({
      erro:  'Chave CNJ não configurada',
      dica:  'Crie um arquivo server/.env com CNJ_API_KEY=<sua_chave>',
      ajuda: 'https://datajud-wiki.cnj.jus.br/api-publica/acesso',
    });
  }

  // Consulta todos os tribunais em paralelo
  const resultados = await Promise.allSettled(
    TODOS_TRIBUNAIS.map(t => consultarTribunal(t, cpf))
  );

  const processos = resultados
    .filter(r => r.status === 'fulfilled')
    .flatMap(r => r.value);

  // Agrupa por tipo
  const grupos = {
    estaduais: processos.filter(p => TRIBUNAIS_ESTADUAIS.includes(p.tribunal.toLowerCase())),
    federais:  processos.filter(p => TRIBUNAIS_FEDERAIS.includes(p.tribunal.toLowerCase())),
    trabalho:  processos.filter(p => TRIBUNAIS_TRABALHO.includes(p.tribunal.toLowerCase())),
    superiores:processos.filter(p => SUPERIORES.includes(p.tribunal.toLowerCase())),
  };

  res.json({
    cpf:                   cpfFmt,
    cpfValido:             true,
    processos,
    grupos,
    totalProcessos:        processos.length,
    tribunaisConsultados:  TODOS_TRIBUNAIS.length,
    tribunaisComResultado: [...new Set(processos.map(p => p.tribunal))],
    dataConsulta:          new Date().toISOString(),
  });
});

// ---------------------------------------------------------------------------
app.listen(PORT, () => {
  console.log(`\nCheck House API rodando em http://localhost:${PORT}`);
  console.log(`CNJ_API_KEY: ${CNJ_API_KEY ? '✅ configurada' : '❌ não configurada (crie server/.env)'}`);
  console.log(`Tribunais: ${TODOS_TRIBUNAIS.length} configurados\n`);
});

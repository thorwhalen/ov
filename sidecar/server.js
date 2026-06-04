// ov Node sidecar — JS-only reverse-engineering over newline-delimited JSON-RPC 2.0 on stdio.
//
// Why a sidecar: the mature source-map / AST tooling is JavaScript; orchestration,
// scoring and persistence stay in Python (see ov/analysis/arch/sidecar.py). The
// contract is a small set of PURE, STATELESS functions. Transport is stdio (the
// same MCP uses) so there is no port to manage and no network exposure of a
// process that ingests untrusted JS.
//
// SAFETY (load-bearing): literal recovery is STATIC AST extraction via @babel/parser
// only. This process NEVER eval()s or executes downloaded JS. If dynamic execution
// were ever required it would go in a disposable, network-isolated headless browser.

'use strict';

const readline = require('readline');

let sourceMap = null;
let babelParser = null;
try { sourceMap = require('source-map'); } catch (e) { /* optional */ }
try { babelParser = require('@babel/parser'); } catch (e) { /* optional */ }

const methods = {
  // consumeSourceMap({mapJson}) -> {files:[{path, content}], sources}
  async consumeSourceMap({ mapJson }) {
    if (!sourceMap) throw new Error('source-map not installed (npm install)');
    const consumer = await new sourceMap.SourceMapConsumer(JSON.parse(mapJson));
    const sources = consumer.sources || [];
    const contents = consumer.sourcesContent || [];
    const files = sources.map((path, i) => ({ path, content: contents[i] || null }));
    if (consumer.destroy) consumer.destroy();
    return { files, sources };
  },

  // extractLiterals({jsText}) -> {strings, urls, routes}  (static AST walk; no eval)
  extractLiterals({ jsText }) {
    if (!babelParser) throw new Error('@babel/parser not installed (npm install)');
    const ast = babelParser.parse(jsText, {
      sourceType: 'unambiguous', errorRecovery: true, plugins: ['jsx'],
    });
    const strings = new Set(), urls = new Set(), routes = new Set();
    const visit = (node) => {
      if (!node || typeof node !== 'object') return;
      if (node.type === 'StringLiteral' && typeof node.value === 'string') {
        const v = node.value;
        if (v.length < 300) strings.add(v);
        if (/^https?:\/\//.test(v)) urls.add(v);
        else if (/^\/[A-Za-z0-9/_:.-]*$/.test(v) && v.length > 1) routes.add(v);
      }
      for (const k in node) {
        const c = node[k];
        if (Array.isArray(c)) c.forEach(visit);
        else if (c && typeof c === 'object' && typeof c.type === 'string') visit(c);
      }
    };
    visit(ast.program);
    return {
      strings: [...strings].slice(0, 500),
      urls: [...urls].slice(0, 200),
      routes: [...routes].slice(0, 200),
    };
  },

  // unpackBundle({jsText}) -> {modules}  (best-effort without webcrack)
  unpackBundle({ jsText }) {
    return {
      modules: [{ name: 'bundle', size: (jsText || '').length }],
      note: 'install webcrack/wakaru in the sidecar for real module unpacking',
    };
  },

  // health check
  ping() { return { ok: true, sourceMap: !!sourceMap, babelParser: !!babelParser }; },
};

const rl = readline.createInterface({ input: process.stdin, terminal: false });
rl.on('line', async (line) => {
  if (!line.trim()) return;
  let id = null;
  try {
    const req = JSON.parse(line);
    id = req.id != null ? req.id : null;
    const fn = methods[req.method];
    if (!fn) throw new Error('unknown method: ' + req.method);
    const result = await fn(req.params || {});
    process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result }) + '\n');
  } catch (e) {
    process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, error: { message: String((e && e.message) || e) } }) + '\n');
  }
});

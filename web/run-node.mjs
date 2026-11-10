// Drive the browser build from Node: node web/run-node.mjs NET < commands.
// Lines are UCI commands; "wait <ms>" pauses before the next one.
import { readFile } from 'node:fs/promises';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';

const dist = process.env.HB_DIST ? process.env.HB_DIST.replace(/\/?$/, '/') : fileURLToPath(new URL('./dist/', import.meta.url));
const make = (await import(dist + 'hypebeast.js')).default;
const engine = await make({ onExit: (code) => process.exit(code) });
engine.listen = (line) => console.log(line);
engine.onError = (line) => console.error(line);
const lines = [];
for await (const line of createInterface({ input: process.stdin })) lines.push(line);
for (const line of lines) {
  if (line.startsWith('wait ')) await new Promise((r) => setTimeout(r, Number(line.slice(5))));
  else if (line.startsWith('net ')) engine.setNnueBuffer(new Uint8Array(await readFile(line.slice(4))), 0);
  else engine.uci(line);
}

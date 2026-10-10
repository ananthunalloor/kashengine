const {spawnSync} = require('node:child_process');
const path = require('node:path');

const script = path.join(__dirname, 'generate_api_reference.py');
const requestedArgs = process.argv.slice(2);
const candidates =
  process.platform === 'win32'
    ? [
        {command: 'py', prefix: ['-3']},
        {command: 'python', prefix: []},
      ]
    : [
        {command: 'python3', prefix: []},
        {command: 'python', prefix: []},
      ];

for (const candidate of candidates) {
  const result = spawnSync(candidate.command, [...candidate.prefix, script, ...requestedArgs], {
    stdio: 'inherit',
  });
  if (result.error && result.error.code === 'ENOENT') {
    continue;
  }
  if (result.error) {
    process.stderr.write(`${result.error.message}\n`);
    process.exit(1);
  }
  process.exit(result.status ?? 1);
}

process.stderr.write(
  'Python was not found. Install Python 3.10 or later, or run the documentation site in the project Docker environment.\n',
);
process.exit(1);

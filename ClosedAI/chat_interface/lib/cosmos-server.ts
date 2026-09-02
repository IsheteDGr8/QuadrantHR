import "server-only"

import { CosmosClient, type Container, type Database } from "@azure/cosmos"

/**
 * Server-only Cosmos DB access for the app's own data (intake tickets, work
 * items). Reuses the same account as the HR agent. Never import this from a
 * client component — the account key lives in these env vars.
 */

function readEnv(...names: string[]): string {
  for (const name of names) {
    const raw = process.env[name]
    if (!raw) continue
    const value = raw.trim().replace(/^['"]|['"]$/g, "")
    // Skip encrypted (`gAAAAA…`) or unresolved (`${…}`) placeholders.
    if (value && !value.startsWith("gAAAAA") && !value.startsWith("${")) return value
  }
  return ""
}

let clientPromise: Promise<CosmosClient> | null = null
const containerCache = new Map<string, Promise<Container>>()

export function isCosmosConfigured(): boolean {
  const conn = readEnv("COSMOS_CONNECTION_STRING")
  if (conn) return true
  return Boolean(readEnv("COSMOS_ENDPOINT", "COSMOS_URI") && readEnv("COSMOS_KEY"))
}

function getClient(): Promise<CosmosClient> {
  if (clientPromise) return clientPromise
  clientPromise = (async () => {
    const conn = readEnv("COSMOS_CONNECTION_STRING")
    if (conn) return new CosmosClient(conn)
    const endpoint = readEnv("COSMOS_ENDPOINT", "COSMOS_URI")
    const key = readEnv("COSMOS_KEY")
    if (!endpoint || !key) {
      throw new Error(
        "Cosmos is not configured. Set COSMOS_CONNECTION_STRING or COSMOS_ENDPOINT + COSMOS_KEY.",
      )
    }
    return new CosmosClient({ endpoint, key })
  })()
  return clientPromise
}

function getDatabaseName(): string {
  // Prefer the greenfield DB. Legacy `closedai-db` is left untouched.
  return readEnv("COSMOS_DATABASE", "COSMOS_DATABASE_NAME") || "closedai-hr"
}

async function getDatabase(): Promise<Database> {
  const client = await getClient()
  const { database } = await client.databases.createIfNotExists({ id: getDatabaseName() })
  return database
}

/**
 * Returns a container, creating it (and the database) on first use. Cached per
 * (container, partitionKey) so we only pay the create-if-not-exists round trip
 * once per process.
 */
export async function getContainer(
  id: string,
  partitionKeyPath = "/status",
): Promise<Container> {
  const cacheKey = `${id}::${partitionKeyPath}`
  const cached = containerCache.get(cacheKey)
  if (cached) return cached
  const promise = (async () => {
    const database = await getDatabase()
    const { container } = await database.containers.createIfNotExists({
      id,
      partitionKey: { paths: [partitionKeyPath] },
    })
    return container
  })()
  containerCache.set(cacheKey, promise)
  return promise
}

export const CONTAINERS = {
  intakeTickets: "intake_tickets",
  // App-owned work queue. Deliberately NOT the legacy `work_items` container —
  // that holds stale experimental docs (snake_case, unknown partition key) and
  // the DB redesign plan defers it. This one uses a known `/id` partition key.
  workItems: "work_queue",
} as const

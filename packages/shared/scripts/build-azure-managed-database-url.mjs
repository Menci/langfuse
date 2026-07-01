#!/usr/bin/env node
// Prints a Postgres URL derived from DATABASE_URL with an Azure AAD access
// token substituted as the password. Used by web/entrypoint.sh under
// DATABASE_AUTH_METHOD=azure-managed-identity so `prisma migrate deploy` and
// `prisma db execute` — both of which read DATABASE_URL directly rather than
// going through the runtime driver adapter — can authenticate.
//
// Migrations complete in seconds; one token is enough for the whole bootstrap.

import { DefaultAzureCredential, ManagedIdentityCredential } from "@azure/identity";
import { env } from "node:process";

const AZURE_POSTGRES_SCOPE = "https://ossrdbms-aad.database.windows.net/.default";

const clientId = env.DATABASE_AZURE_CLIENT_ID;
const databaseUrl = env.DATABASE_URL;

if (!databaseUrl) {
  process.stderr.write("DATABASE_URL is not set\n");
  process.exit(1);
}

const credential = clientId
  ? new ManagedIdentityCredential({ clientId })
  : new DefaultAzureCredential();

const token = await credential.getToken(AZURE_POSTGRES_SCOPE);
if (!token) {
  process.stderr.write(
    `Azure credential returned no token for scope ${AZURE_POSTGRES_SCOPE}\n`,
  );
  process.exit(1);
}

const url = new URL(databaseUrl);
url.password = token.token;

process.stdout.write(url.toString());

// This file exports the prisma db connection, the Prisma Object, and the Typescript types.
// This is not imported in the index.ts file of this package, as we must not import this into FE code.

import { PrismaPg } from "@prisma/adapter-pg";
import { Prisma, PrismaClient } from "@prisma/client";
import { Pool } from "pg";
import { env } from "process";
import { getAzureCredential } from "./server/auth/credentials";
import { logger } from "./server";

const AZURE_POSTGRES_SCOPE =
  "https://ossrdbms-aad.database.windows.net/.default";

export class PrismaClientSingleton {
  private static instance: PrismaClient;

  public static getInstance(): PrismaClient {
    if (PrismaClientSingleton.instance) {
      return PrismaClientSingleton.instance;
    }

    PrismaClientSingleton.instance = createPrismaInstance();

    return PrismaClientSingleton.instance;
  }
}

// pg calls the password callback once per new pool client (not per query). So a
// long-lived pool naturally picks up a rotated AAD token whenever a fresh
// client is established (idle timeout, server-side disconnect, pool grow).
//
// We parse DATABASE_URL manually into explicit fields rather than passing
// connectionString to Pool: pg-connection-string surfaces a missing password
// as an empty string, and pg-pool then treats the password field as "defined"
// and never calls the async callback. Feeding host/port/user/database as
// separate options keeps the callback authoritative.
const createAzureManagedPgPool = (): Pool => {
  if (!env.DATABASE_URL) {
    throw new Error("DATABASE_URL is required under azure-managed-identity");
  }
  const url = new URL(env.DATABASE_URL);
  const sslmode = url.searchParams.get("sslmode");
  const sslEnabled = sslmode !== "disable" && sslmode !== undefined;
  return new Pool({
    host: url.hostname,
    port: url.port ? Number(url.port) : 5432,
    user: decodeURIComponent(url.username),
    database: url.pathname.replace(/^\//, ""),
    ssl: sslEnabled ? { rejectUnauthorized: false } : false,
    password: async () => {
      const credential = getAzureCredential(env.DATABASE_AZURE_CLIENT_ID);
      const token = await credential.getToken(AZURE_POSTGRES_SCOPE);
      if (!token) {
        throw new Error(
          `Azure credential returned no token for scope ${AZURE_POSTGRES_SCOPE}`,
        );
      }
      return token.token;
    },
  });
};

const createPrismaInstance = () => {
  const useManagedIdentity =
    env.DATABASE_AUTH_METHOD === "azure-managed-identity";

  const clientOptions: Prisma.PrismaClientOptions = {
    log: [
      { emit: "event", level: "query" },
      { emit: "event", level: "error" },
      { emit: "event", level: "warn" },
    ],
  };

  if (useManagedIdentity) {
    clientOptions.adapter = new PrismaPg(createAzureManagedPgPool(), {
      // Let Prisma close the pool on $disconnect so a graceful shutdown
      // drains sockets rather than leaking them.
      disposeExternalPool: true,
    });
  }

  const client = new PrismaClient<
    Prisma.PrismaClientOptions,
    "warn" | "error" | "query"
  >(clientOptions);

  if (env.NODE_ENV === "development") {
    client.$on("query", (event) => {
      logger.info(`prisma:query ${event.query}, ${event.duration}ms`);
    });
  }

  client.$on("warn", (event) => {
    logger.warn(`prisma:warn ${event.message}`);
  });

  client.$on("error", (event) => {
    logger.error(`prisma:error ${event.message}`);
  });
  return client;
};

declare const globalThis: {
  prismaGlobal: PrismaClient | undefined;
} & typeof global;

// eslint-disable-next-line turbo/no-undeclared-env-vars
if (process.env.NODE_ENV === "development") {
  globalThis.prismaGlobal ??= createPrismaInstance(); // regular instantiation
}

export const prisma =
  globalThis.prismaGlobal ?? PrismaClientSingleton.getInstance();

export * from "@prisma/client";

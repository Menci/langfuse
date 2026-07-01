import { beforeEach, describe, expect, it, vi } from "vitest";

const defaultCredentialCtor = vi.fn();
const managedIdentityCredentialCtor = vi.fn();

vi.mock("@azure/identity", () => {
  class DefaultAzureCredential {
    getToken = vi.fn();

    constructor() {
      defaultCredentialCtor();
    }
  }

  class ManagedIdentityCredential {
    readonly clientId: string;
    getToken = vi.fn();

    constructor(options: { clientId: string }) {
      this.clientId = options.clientId;
      managedIdentityCredentialCtor(options);
    }
  }

  return { DefaultAzureCredential, ManagedIdentityCredential };
});

import {
  __resetAzureCredentialCacheForTests,
  createAzureManagedCredentialProvider,
  getAzureCredential,
} from "./azureCredentials";

beforeEach(() => {
  __resetAzureCredentialCacheForTests();
  defaultCredentialCtor.mockClear();
  managedIdentityCredentialCtor.mockClear();
});

describe("getAzureCredential", () => {
  it("returns a singleton per clientId", () => {
    const a1 = getAzureCredential("client-a");
    const a2 = getAzureCredential("client-a");
    expect(a1).toBe(a2);
    expect(managedIdentityCredentialCtor).toHaveBeenCalledTimes(1);
    expect(managedIdentityCredentialCtor).toHaveBeenCalledWith({
      clientId: "client-a",
    });
  });

  it("returns distinct singletons for different clientIds", () => {
    const a = getAzureCredential("client-a");
    const b = getAzureCredential("client-b");
    expect(a).not.toBe(b);
    expect(managedIdentityCredentialCtor).toHaveBeenCalledTimes(2);
  });

  it("uses DefaultAzureCredential when clientId is omitted", () => {
    const d1 = getAzureCredential();
    const d2 = getAzureCredential();
    expect(d1).toBe(d2);
    expect(defaultCredentialCtor).toHaveBeenCalledTimes(1);
    expect(managedIdentityCredentialCtor).not.toHaveBeenCalled();
  });
});

describe("createAzureManagedCredentialProvider", () => {
  it("exposes name and username on the provider surface", () => {
    const provider = createAzureManagedCredentialProvider({
      name: "redis-primary",
      scope: "https://redis.azure.com/.default",
      clientId: "client-a",
      username: "principal@tenant",
    });
    expect(provider.name).toBe("redis-primary");
    expect(provider.username).toBe("principal@tenant");
  });

  it("fetches a token using the underlying credential and the configured scope", async () => {
    const credential = getAzureCredential("client-a");
    vi.mocked(credential.getToken).mockResolvedValue({
      token: "aad-token",
      expiresOnTimestamp: 1_700_000_000_000,
    });

    const provider = createAzureManagedCredentialProvider({
      name: "redis-primary",
      scope: "https://redis.azure.com/.default",
      clientId: "client-a",
    });

    await expect(provider.fetchToken()).resolves.toEqual({
      token: "aad-token",
      expiresOnTimestamp: 1_700_000_000_000,
    });
    expect(credential.getToken).toHaveBeenCalledWith(
      "https://redis.azure.com/.default",
    );
  });

  it("throws when the credential returns null", async () => {
    const credential = getAzureCredential("client-a");
    vi.mocked(credential.getToken).mockResolvedValue(null);

    const provider = createAzureManagedCredentialProvider({
      name: "redis-primary",
      scope: "https://redis.azure.com/.default",
      clientId: "client-a",
    });

    await expect(provider.fetchToken()).rejects.toThrow(
      /Azure credential returned no token for scope https:\/\/redis\.azure\.com\/\.default/,
    );
  });

  it("propagates errors from the credential", async () => {
    const credential = getAzureCredential("client-a");
    vi.mocked(credential.getToken).mockRejectedValue(
      new Error("IMDS unreachable"),
    );

    const provider = createAzureManagedCredentialProvider({
      name: "redis-primary",
      scope: "https://redis.azure.com/.default",
      clientId: "client-a",
    });

    await expect(provider.fetchToken()).rejects.toThrow("IMDS unreachable");
  });
});

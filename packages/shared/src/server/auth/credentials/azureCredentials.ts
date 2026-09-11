import {
  DefaultAzureCredential,
  ManagedIdentityCredential,
  type TokenCredential,
} from "@azure/identity";

import type { ManagedCredentialProvider } from "./types";

// Downstream Azure SDKs cache access tokens on the credential instance, so
// callers targeting the same identity must share one credential to share the
// cache. Undefined key = process-default identity (DefaultAzureCredential).
const credentialCache = new Map<string | undefined, TokenCredential>();

export const getAzureCredential = (clientId?: string): TokenCredential => {
  let credential = credentialCache.get(clientId);
  if (!credential) {
    credential = clientId
      ? new ManagedIdentityCredential({ clientId })
      : new DefaultAzureCredential();
    credentialCache.set(clientId, credential);
  }
  return credential;
};

export interface AzureManagedCredentialProviderOptions {
  name: string;
  scope: string;
  clientId?: string;
  username?: string;
}

// Adapter that lets a subsystem which cannot consume a TokenCredential directly
// (ioredis has no async credential hook) receive push-model token refreshes via
// RefreshingTokenManager.
export const createAzureManagedCredentialProvider = (
  options: AzureManagedCredentialProviderOptions,
): ManagedCredentialProvider => {
  const credential = getAzureCredential(options.clientId);
  return {
    name: options.name,
    username: options.username,
    fetchToken: async () => {
      const token = await credential.getToken(options.scope);
      if (!token) {
        throw new Error(
          `Azure credential returned no token for scope ${options.scope}`,
        );
      }
      return {
        token: token.token,
        expiresOnTimestamp: token.expiresOnTimestamp,
      };
    },
  };
};

// Reset the per-clientId credential cache between test cases. Not part of the
// production surface.
export const __resetAzureCredentialCacheForTests = (): void => {
  credentialCache.clear();
};

# Azure Workload Identity deployment (evaluation-wcus)

Reference deployment for the fork's `azure-wi` fleet — the compliance
target is "no service outside Azure, no static credentials." Everything
in the runtime plane (Postgres, Redis, Blob, Azure OpenAI, CH backup)
authenticates through the shared user-assigned identity
`evaluation-langfuse-wi`, federated to the
`langfuse/langfuse-workload-sa` Kubernetes ServiceAccount.

## Prerequisites

The manifests assume the following Azure resources exist:

| Resource | Purpose |
| --- | --- |
| AKS cluster with `--enable-workload-identity --enable-oidc-issuer` | Cluster |
| L-series nodepool with `--node-taints workload=clickhouse:NoSchedule --labels workload=clickhouse` | CH data plane (local NVMe) |
| User-assigned identity | Runtime credential for all data services |
| Federated credential: `system:serviceaccount:langfuse:langfuse-workload-sa` | Bind SA to UAI |
| Postgres Flexible Server with Entra admin = the UAI | App metadata |
| Azure Managed Redis Enterprise (`accessKeysAuthentication: Disabled`, `clusteringPolicy: EnterpriseCluster`) | BullMQ backend |
| Storage Account with 4 blob containers: `langfuse-events`, `langfuse-media`, `langfuse-batch-export`, `langfuse-clickhouse-backup` | Event uploads + backups |
| Azure OpenAI resource | LLM adapter |
| Altinity ClickHouse Operator installed cluster-wide | CHI + CHK CRDs |

RBAC to grant the UAI:
- Postgres: `microsoft-entra-admin` on the flexible server
- Redis: `Redis Data Contributor` access-policy assignment
- Storage: `Storage Blob Data Owner` on the storage account
- Azure OpenAI: `Cognitive Services User`

## Apply order

Manifests are numbered so `kubectl apply -f k8s/` in lexical order works.
The only file that isn't checked in verbatim is
`01-app-secret.template.yaml`; substitute values first.

```
kubectl apply -f k8s/00-namespace-sa.yaml
envsubst < k8s/01-app-secret.template.yaml | kubectl apply -f -
kubectl apply -f k8s/02-env.yaml
kubectl apply -f k8s/05-local-nvme-prep.yaml    # wait for `local-nvme` PVs
kubectl apply -f k8s/08-clickhouse-keeper.yaml  # wait for chk Completed
kubectl apply -f k8s/10-clickhouse-chi.yaml     # wait for chi Completed
kubectl apply -f k8s/20-langfuse-web.yaml
kubectl apply -f k8s/21-langfuse-worker.yaml
```

Every step is idempotent; re-apply is safe.

## Runtime-tuned bits pinned in the manifests

- `CLICKHOUSE_MIGRATION_URL` pins to `chi-langfuse-default-0-0` (not the
  load-balanced service). `ON CLUSTER default` DDL only broadcasts to
  replicas the initiator sees in its own cluster config at submission
  time; hitting a replica whose config hasn't picked up its peer yields
  DDL that stays permanently in a "no local address in host list" state.
- Redis fork patches (`packages/shared/src/server/redis/redis.ts`):
  hash-tag queue prefixes for MI mode (Azure Managed Redis Enterprise is
  sharded server-side even under `EnterpriseCluster` policy),
  `applyAzureManagedIdentityAuth` pre-seeds `condition` synchronously,
  and `.duplicate()` is monkey-patched so BullMQ's blocking-connection
  clone gets its own token manager.
- Postgres fork patches (`packages/shared/src/db.ts`): DATABASE_URL is
  parsed into explicit `host/port/user/database` fields — feeding
  `connectionString` to pg-pool would surface a missing password as an
  empty string and skip the async token callback entirely.
- CH data lives on ephemeral local NVMe (`Standard_L8s_v4`, ~1.79 TB per
  node, 550k read / 220k write IOPS). Durability is `ReplicatedMergeTree`
  2-replica + `clickhouse-backup` sidecar (hourly incremental, daily
  full, 7-day retention, uploaded to `langfuse-clickhouse-backup` via
  workload identity).

## Restore procedure (validated 2026-07-02)

Restore into a scratch database on the live cluster:

```
kubectl -n langfuse exec chi-langfuse-default-0-0-0 -c clickhouse-backup -- \
  clickhouse-backup restore_remote \
    --tables=default.<TABLE> \
    --restore-database-mapping=default:<SCRATCH_DB> \
    --schema --data <BACKUP_NAME>
```

`clickhouse-backup list remote` prints the available backup names (format
`shard0-full-YYYYMMDDHHMMSS` / `shard0-increment-…`) plus stored size and
whether the backup is full or delta-linked to a parent.

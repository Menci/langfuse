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

# Geneva telemetry (mdsd + fluentd + mdm) — see "Geneva onboarding" below
kubectl apply -f k8s/29-geneva-rbac.yaml
kubectl apply -f k8s/30-geneva-services.yaml
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

## Geneva onboarding

The DaemonSet reuses the existing `SocietasLogNonProd` Geneva account
(also used by the societas project) — same account owner, same cert
identity, same MDM/MDSD auth id
(`dev.geneva.keyvault.societas-test.microsoft.com`).
`MONITORING_ROLE` is set to `SocietasLogNonProd` (same string societas
uses; ROLE is the Geneva account name, not a per-workload identifier).
Our data is namespaced by `MONITORING_TENANT: aks-evaluation-wcus`.

Cert distribution:

- `evaluation-langfuse-kv` (Key Vault in the Evaluation RG) holds a
  KV-managed certificate `geneva-cert`. The issuer `PrivateCA` is a
  named alias for provider `OneCertV2-PrivateCA` (Microsoft internal
  PKI, same setup as societasKeyVault).
- The cert policy mirrors societas' exactly: RSA 2048, EKU
  serverAuth+clientAuth, keyUsage digitalSignature+keyEncipherment,
  subject `CN=geneva.keyvault.societas-test.microsoft.com`, five SANs
  spanning `{dev,test,dogfood,stress,staging}.geneva.keyvault.societas-test.microsoft.com`,
  6-month validity, AutoRenew at 50% lifetime.
- Because the cert is KV-managed (not imported), OneCert re-issues it
  automatically at 50% of its lifetime; no manual sync from societas is
  required for rotation.
- `SecretProviderClass geneva-kvcert` (via the AKS
  `azureKeyvaultSecretsProvider` addon) mounts it at
  `/geneva/geneva_auth/geneva_cert.pem` inside the mdsd + mdm
  containers, using `langfuse-workload-sa`'s Key Vault Secrets User
  binding.

To re-provision the issuer and cert from scratch on a fresh KV:

```
az keyvault certificate issuer create \
  --vault-name evaluation-langfuse-kv \
  --issuer-name PrivateCA \
  --provider OneCertV2-PrivateCA

az keyvault certificate create \
  --vault-name evaluation-langfuse-kv \
  --name geneva-cert \
  --policy '{...policy JSON mirroring societaskeyvault/certificates/geneva-cert/policy...}'
```

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

## SpreadsheetBench evaluation gate

First business workload on this Langfuse deployment: the objective
(golden-answer) evaluator from
[SpreadsheetBench](https://github.com/RUCKBReasoning/SpreadsheetBench)
Verified-400, wrapped as reusable Kubernetes Jobs.

Layered on top of Langfuse SDK v4 `DatasetClient.run_experiment()`, so
the SDK owns per-item Trace + DatasetRunItem + Score wiring. Wrapper
scripts under `eval/wrapper/` are mounted through the
`spreadsheet-bench-wrapper` ConfigMap (not baked into the image), so
iteration on the Langfuse-integration layer is a `kubectl apply` on the
ConfigMap and does not require rebuilding
`societasdev.azurecr.io/langfuse-eval/spreadsheet-bench`.

Vendored spreadsheet-bench code + the Verified-400 dataset are CC BY-SA
4.0; see `eval/spreadsheet-bench/{NOTICE,LICENSE}.md`.

### Apply order

```
# One-time image build (Kaniko job on kaniko-build ns, git-context
# from this branch, Dockerfile at deploy/azure-wi/eval/Dockerfile)
kubectl apply -f k8s/49-spreadsheet-bench-wrapper-cm.yaml
kubectl apply -f k8s/50-spreadsheet-bench-selftest.yaml    # Phase 0: PVC + selftest
kubectl apply -f k8s/51-spreadsheet-bench-import.yaml      # one-shot: 400 items → dataset
kubectl apply -f k8s/52-spreadsheet-bench-eval-init.yaml   # baseline: init xlsx as predicted
```

The selftest job also downloads the ~15 MB Verified-400 tarball into the
`spreadsheet-bench-data` PVC; subsequent import + eval jobs reuse it
without redownload.

### Running a real skill's outputs

The eval job scores whatever xlsx directory it's pointed at. To score a
skill run, produce `/predicted/<task_id>.xlsx` files somewhere (either
inside the cluster on a new PVC, or on the existing PVC under a
subdirectory) and copy `k8s/52-spreadsheet-bench-eval-init.yaml` into a
new job spec that changes:

- `--run-name=<label>`  identifies the run in the Langfuse UI compare
- `--predicted-dir=<path>` where predicted xlsx sit
- `--predicted-template={task_id}.xlsx` the default flat layout; use a
  template with slashes only for baseline reuses of the dataset tree

Pass rate + per-task diff detail land on the Langfuse dataset. Compare
UI at `Datasets → spreadsheet-bench-v400 → Runs` cross-tabulates runs.

### Cross-run baseline

`init-baseline` (no-op skill = identity xlsx) is the floor. Verified
2026-07-08: 1/400 pass (0.25%) — one task's golden happens to equal its
init. Any real skill run should beat this.

### Auth surface

- `spreadsheet-bench-langfuse-creds` Secret holds project-scoped
  pk/sk for the `excel-skill-eval` project inside the `Evaluation`
  organization. Bootstrap via a Prisma `apiKey.create` call (see git
  log for the ad-hoc snippet).
- Everything else (Postgres for dataset writes, ClickHouse for trace /
  score writes) is reached in-cluster and reuses the
  `langfuse-workload-sa` chain already set up for web / worker.

import { env } from "@/src/env.mjs";
import { hasEntitlementBasedOnPlan } from "@/src/features/entitlements/server/hasEntitlement";
import { getSelfHostedInstancePlanServerSide } from "@/src/features/entitlements/server/getPlan";

// Restrict organization creation to instance administrators (users.admin=true).
// The fork's single-team invitation-only deployment gives access via invitation
// into a pre-existing organization — anyone else logging in via OAuth should
// not be able to spin up their own parallel organization. Non-admins still
// see the "no organizations" empty state until an admin invites them.
//
// The upstream entitlement-gated allowlist below still applies on Enterprise:
// admins are always allowed; non-admins fall back to the allowlist when the
// entitlement is present.
export function canCreateOrganizations(
  user: {
    email?: string | null;
    admin?: boolean | null;
  } | null,
): boolean {
  if (user?.admin) return true;

  const instancePlan = getSelfHostedInstancePlanServerSide();
  const entitlementActive =
    !!env.LANGFUSE_ALLOWED_ORGANIZATION_CREATORS &&
    hasEntitlementBasedOnPlan({
      plan: instancePlan,
      entitlement: "self-host-allowed-organization-creators",
    });

  if (!entitlementActive) {
    // Without an explicit allowlist entitlement, non-admins cannot create
    // organizations in this fork.
    return false;
  }

  if (!user?.email) return false;
  const allowedOrgCreators = env
    .LANGFUSE_ALLOWED_ORGANIZATION_CREATORS!.toLowerCase()
    .split(",");
  return allowedOrgCreators.includes(user.email.toLowerCase());
}
